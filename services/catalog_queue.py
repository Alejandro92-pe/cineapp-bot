"""Durable, bounded local catalogue worker. No Supabase or application imports."""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from providers.vimeus import integer, ImportFailure
from providers.tmdb import trailer_url, tmdb_rating
from services.vimeus_import import build_manifest, image_url

KINDS = {'movies': 'pelicula', 'series': 'serie', 'animes': 'anime'}


class BatchPause(BaseException):
    """Must escape optional TMDB metadata fallbacks; never publish partial work."""


@contextmanager
def worker_lock(path):
    """OS releases the lock even if the process dies. Only one worker may recover jobs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as file:
        file.seek(0)
        if __import__('os').fstat(file.fileno()).st_size == 0:
            file.write(b'0'); file.flush()
        file.seek(0)
        try:
            if __import__('os').name == 'nt':
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ImportFailure('Ya hay un importador trabajando en esta cola.') from None
        try:
            yield
        finally:
            file.seek(0)
            if __import__('os').name == 'nt':
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)


class CatalogQueue:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS jobs (
              kind TEXT NOT NULL, tmdb INTEGER NOT NULL, source TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
              ready REAL NOT NULL DEFAULT 0, manifest TEXT, note TEXT,
              PRIMARY KEY(kind,tmdb));
            CREATE TABLE IF NOT EXISTS cursors(resource TEXT PRIMARY KEY, page INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,payload TEXT NOT NULL,expires REAL NOT NULL);
        ''')

    def get_setting(self, key):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else 0

    def set_setting(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key,value))

    def discover(self, provider, resource):
        if resource not in KINDS: raise ImportFailure('Tipo de listado no permitido.')
        row = self.db.execute('SELECT page FROM cursors WHERE resource=?', (resource,)).fetchone()
        page = row[0] if row else 1
        if page == 0: return 0
        rows, pagination = provider.page(resource, page)
        # Validate the whole page before committing either jobs or cursor.
        values = [(KINDS[resource], integer(r.get('tmdb_id'),1), json.dumps(r)) for r in rows]
        before = self.db.total_changes
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO jobs(kind,tmdb,source) VALUES (?,?,?)', values)
            added = self.db.total_changes - before
            self.db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)',
                            (resource, page+1 if pagination['has_next'] else 0))
        return added

    def recover(self):
        with self.db:
            self.db.execute("UPDATE jobs SET status='pending' WHERE status='running'")

    def run(self, provider, tmdb_get, limit=3, transport=None):
        results = []
        self.recover()  # Caller holds worker_lock for discovery + all processing.
        for _ in range(limit):
            row = self.db.execute("SELECT * FROM jobs WHERE status='pending' AND ready<=? ORDER BY rowid LIMIT 1",
                                  (self.clock(),)).fetchone()
            if not row: break
            key = (row['kind'],row['tmdb'])
            with self.db:
                self.db.execute("UPDATE jobs SET status='running' WHERE kind=? AND tmdb=?",key)
            try:
                if row['kind']=='pelicula':
                    document, warnings = movie_manifest(json.loads(row['source']),tmdb_get)
                else:
                    document, warnings = build_manifest(provider,row['tmdb'],row['kind'],tmdb_get,metadata_seconds=600)
                with self.db:
                    self.db.execute("UPDATE jobs SET status='done',manifest=?,note=? WHERE kind=? AND tmdb=?",
                                    (json.dumps(document),json.dumps(warnings),*key))
                results.append({'kind':key[0],'tmdb':key[1],'status':'done',
                                'title':document['contenido']['titulo'], 'seasons':len(document['temporadas']),
                                'episodes':sum(len(s['capitulos']) for s in document['temporadas']), 'warnings':warnings})
            except BatchPause:
                with self.db:
                    self.db.execute("UPDATE jobs SET status='pending' WHERE kind=? AND tmdb=?",key)
                break
            except Exception as error:
                attempts = row['attempts']+1
                # Never store a Requests exception: its URL may contain a private key.
                note = str(error) if isinstance(error,ImportFailure) else 'Lectura externa incompleta; pendiente de reintento.'
                with self.db:
                    self.db.execute('UPDATE jobs SET status=?,attempts=?,ready=?,note=? WHERE kind=? AND tmdb=?',
                        ('failed' if attempts>=3 else 'pending',attempts,self.clock()+min(3600,60*2**attempts),note,*key))
                results.append({'kind':key[0],'tmdb':key[1],'status':'pending' if attempts<3 else 'failed','reason':note})
        return results

    def summary(self):
        return {r[0]:r[1] for r in self.db.execute('SELECT status,count(*) FROM jobs GROUP BY status')}


class PacedTransport:
    """One shared persisted gate for both APIs, including Retry-After and restarts."""
    def __init__(self, queue, seconds=1.2, max_seconds=180, session=None, sleep=time.sleep, clock=time.time):
        self.queue,self.seconds,self.session = queue,seconds,session or requests.Session()
        self.sleep,self.clock,self.deadline = sleep,clock,clock()+max_seconds
        self.requests,self.waited = 0,0

    def get(self,url,**kwargs):
        wait = max(0,self.queue.get_setting('next_request')-self.clock())
        if self.clock()+wait>=self.deadline: raise BatchPause()
        if wait: self.sleep(wait); self.waited+=wait
        # Reserve before request, so a crash cannot erase rate pacing.
        self.queue.set_setting('next_request',self.clock()+self.seconds)
        self.requests+=1
        try:
            response=self.session.get(url,**kwargs)
        except requests.RequestException:
            self.queue.set_setting('next_request',self.clock()+30)
            raise BatchPause() from None
        if response.status_code in (429,500,502,503,504):
            delay=60
            value=response.headers.get('Retry-After','')
            try: delay=max(delay,float(value))
            except ValueError:
                try: delay=max(delay,parsedate_to_datetime(value).replace(tzinfo=timezone.utc).timestamp()-self.clock())
                except (ValueError,TypeError,OverflowError): pass
            self.queue.set_setting('next_request',self.clock()+delay)
            raise BatchPause()
        return response


class CachedMetadata:
    def __init__(self, queue, client): self.queue,self.client=queue,client
    def get(self,path,params=None):
        key=json.dumps([path,params or {},'es-MX'],sort_keys=True)
        row=self.queue.db.execute('SELECT payload FROM cache WHERE key=? AND expires>?',(key,self.queue.clock())).fetchone()
        if row: return json.loads(row[0])
        value=self.client.get(path,params)
        with self.queue.db:
            self.queue.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',
                (key,json.dumps(value),self.queue.clock()+86400))
        return value


def movie_manifest(row, get):
    tmdb=integer(row['tmdb_id'],1)
    meta=get(f'/movie/{tmdb}')
    content={'tipo':'pelicula','tmdb_id':tmdb,'titulo':meta.get('title') or row.get('title') or f'TMDB {tmdb}',
             'sinopsis':meta.get('overview',''),'imagen_url':image_url(meta.get('poster_path')),
             'backdrop_url':image_url(meta.get('backdrop_path')).replace('/w500','/w1280'),
             'genero':', '.join(g['name'] for g in meta.get('genres',[]) if g.get('name')),
             'rating':tmdb_rating(meta),'duracion':meta.get('runtime')}
    year=str(meta.get('release_date',''))[:4]
    if year.isdigit(): content['año']=int(year)
    trailer=trailer_url(get,'movie',tmdb)
    if trailer: content['trailer_url']=trailer
    return {'contenido':content,'temporadas':[]},[]


def completed_manifests(path):
    """Read-only publication boundary: pending/failed snapshots never reach the app."""
    path=Path(path)
    if not path.exists(): return []
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT manifest FROM jobs WHERE status='done' ORDER BY rowid")]
