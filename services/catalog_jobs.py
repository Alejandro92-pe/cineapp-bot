"""Durable PostgreSQL import queue. A cron request runs one bounded batch."""
from contextlib import contextmanager
import hashlib
import json
import threading
import time

from sqlalchemy import Table, Column, String, Text, Integer, Float, select, update, delete, text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from security_store import metadata
from services.catalog_queue import KINDS, PacedTransport, BatchPause, movie_manifest
from providers.vimeus import integer, ImportFailure, VimeusClient
from providers.tmdb import TMDBClient
from services.vimeus_import import build_manifest

jobs = Table('catalog_jobs', metadata,
    Column('kind', String(20), primary_key=True), Column('tmdb', Integer, primary_key=True),
    Column('source', Text, nullable=False), Column('status', String(16), nullable=False),
    Column('attempts', Integer, nullable=False), Column('ready', Float, nullable=False),
    Column('created_at', Float, nullable=False), Column('note', String(300)))
settings = Table('catalog_settings', metadata, Column('key', String(80), primary_key=True), Column('value', Float, nullable=False))
cache = Table('catalog_cache', metadata, Column('key', String(64), primary_key=True), Column('payload', Text, nullable=False), Column('expires', Float, nullable=False))


class DurableQueue:
    pending_states = ('pending',)
    running_states = {'running': 'pending'}
    def __init__(self, store, clock=time.time, job_table=jobs, namespace=""):
        self.jobs, self.namespace = job_table, namespace
        self.engine, self.local, self.clock = store.engine, store.local, clock
        self.insert = sqlite_insert if store.local else pg_insert
        # All queue instances sharing a local store share the production-style lock.
        if not hasattr(store, 'catalog_lock'):
            store.catalog_lock = threading.Lock()
        self.local_lock = store.catalog_lock

    @contextmanager
    def lock(self):
        if self.local:
            acquired = self.local_lock.acquire(blocking=False)
            try: yield acquired
            finally:
                if acquired: self.local_lock.release()
            return
        # Session lock survives intermediate commits; released on disconnect/restart.
        with self.engine.connect() as connection:
            acquired = connection.execute(text('SELECT pg_try_advisory_lock(812194760123)')).scalar_one()
            try: yield acquired
            finally:
                if acquired: connection.execute(text('SELECT pg_advisory_unlock(812194760123)'))

    def get_setting(self, key):
        key = self.namespace + key
        with self.engine.connect() as c:
            return c.execute(select(settings.c.value).where(settings.c.key == key)).scalar_one_or_none() or 0

    def set_setting(self, key, value):
        key = self.namespace + key
        stmt = self.insert(settings).values(key=key, value=value)
        with self.engine.begin() as c:
            c.execute(stmt.on_conflict_do_update(index_elements=['key'], set_={'value': value}))

    def cached(self, key):
        with self.engine.connect() as c:
            value = c.execute(select(cache.c.payload).where(cache.c.key == key, cache.c.expires > self.clock())).scalar_one_or_none()
            return json.loads(value) if value else None

    def save_cache(self, key, payload):
        value = json.dumps(payload)
        if len(value.encode()) > 4*1024*1024: return
        stmt = self.insert(cache).values(key=key, payload=value, expires=self.clock()+86400)
        with self.engine.begin() as c:
            c.execute(stmt.on_conflict_do_update(index_elements=['key'], set_={'payload': value, 'expires': self.clock()+86400}))

    def discover(self, provider, resource):
        jobs = self.jobs
        key = 'page:' + resource
        page = int(self.get_setting(key)) or 1
        finished = self.get_setting('finished:' + resource)
        if finished and finished > self.clock()-86400:
            return 0
        rows, pagination = provider.page(resource, page)
        # Validate the complete page before advancing; duplicate titles remain single jobs.
        batch = [{'kind': KINDS[resource], 'tmdb': integer(r.get('tmdb_id'), 1), 'source': json.dumps(r),
                  'status': 'pending', 'attempts': 0, 'ready': 0, 'created_at': self.clock()} for r in rows]
        with self.engine.begin() as c:
            if batch:
                c.execute(self.insert(jobs).values(batch).on_conflict_do_nothing(index_elements=['kind', 'tmdb']))
            next_page = page+1 if pagination['has_next'] else 1
            c.execute(self.insert(settings).values(key=self.namespace+key, value=next_page).on_conflict_do_update(index_elements=['key'], set_={'value': next_page}))
            if not pagination['has_next']:
                done_key = 'finished:' + resource
                c.execute(self.insert(settings).values(key=self.namespace+done_key, value=self.clock()).on_conflict_do_update(index_elements=['key'], set_={'value': self.clock()}))
        return len(batch)

    def summary(self):
        jobs = self.jobs
        with self.engine.connect() as c:
            result = {}
            for status, count in c.execute(select(jobs.c.status, func.count()).group_by(jobs.c.status)):
                # Keep the existing admin counters compatible with refresh jobs.
                status = {'refresh_pending': 'pending', 'refresh_running': 'running'}.get(status, status)
                result[status] = result.get(status, 0) + count
            return result

    def prepare_work(self):
        """Optional maintenance, after discovery and before claiming one job."""

    def manifest(self, provider, row, get_metadata):
        if row['kind'] == 'pelicula':
            doc, warnings = movie_manifest(json.loads(row['source']), get_metadata)
            doc['contenido']['tmdb_media'] = 'movie'
            return doc, warnings
        return build_manifest(provider, row['tmdb'], row['kind'], get_metadata, metadata_seconds=600)

    def run(self, provider, get_metadata, publish, discover=True):
        jobs = self.jobs
        with self.lock() as acquired:
            if not acquired: return {'busy': True}
            if self.get_setting('batch_after') > self.clock(): return {'waiting': True, 'queue': self.summary()}
            self.set_setting('batch_after', self.clock()+60)
            with self.engine.begin() as c:
                for running, pending in self.running_states.items():
                    c.execute(update(jobs).where(jobs.c.status == running).values(status=pending))
                c.execute(delete(cache).where(cache.c.expires < self.clock()))
            discovery_review = False
            try:
                if discover:
                    resources = ('movies', 'series', 'animes')
                    turn = int(self.get_setting('turn')) % 3
                    self.discover(provider, resources[turn])
                    self.set_setting('turn', turn+1)
            except BatchPause:
                return {'paused': True, 'queue': self.summary()}
            except Exception:
                # A bad provider page must not stop already queued titles or other resources.
                # Keep its page cursor unchanged so it can be retried on the next rotation.
                self.set_setting('turn', turn+1)
                discovery_review = True
            self.prepare_work()
            with self.engine.begin() as c:
                # Discovery and processing have separate cursors. An old backlog
                # of series must not starve newer movies/anime, including on pause.
                kinds = ('pelicula', 'serie', 'anime')
                work_turn = int(self.get_setting('work_turn')) % len(kinds)
                row = None
                for pending in self.pending_states:
                    for step in range(len(kinds)):
                        index = (work_turn + step) % len(kinds)
                        row = c.execute(select(jobs).where(jobs.c.status == pending,
                            jobs.c.ready <= self.clock(), jobs.c.kind == kinds[index])
                            .order_by(jobs.c.created_at, jobs.c.tmdb).limit(1)).mappings().first()
                        if row:
                            stmt = self.insert(settings).values(key=self.namespace+'work_turn', value=(index+1) % len(kinds))
                            c.execute(stmt.on_conflict_do_update(index_elements=['key'], set_={'value': (index+1) % len(kinds)}))
                            break
                    if row: break
                if not row: return {'queue': self.summary(), 'discovery_review': discovery_review}
                row = dict(row)
                target = (jobs.c.kind == row['kind']) & (jobs.c.tmdb == row['tmdb'])
                pending = row['status']
                running = next(k for k, v in self.running_states.items() if v == pending)
                c.execute(update(jobs).where(target).values(status=running))
            try:
                doc, warnings = self.manifest(provider, row, get_metadata)
                # Whole-title RPC is idempotent; a crash after publication only causes a safe reimport.
                publish(doc)
                with self.engine.begin() as c:
                    c.execute(update(jobs).where(target).values(status='done', ready=self.clock()+604800, note='; '.join(warnings)[:300]))
                result = {'imported': 1, 'kind': row['kind'], 'tmdb_id': row['tmdb']}
            except BatchPause:
                with self.engine.begin() as c:
                    c.execute(update(jobs).where(target).values(status=pending, ready=self.clock()+60))
                result = {'paused': True}
            except Exception:
                attempts = row['attempts']+1
                with self.engine.begin() as c:
                    c.execute(update(jobs).where(target).values(status='failed' if attempts >= 3 else pending,
                        attempts=attempts, ready=self.clock()+min(3600, 300*2**attempts), note='ImportaciÃ³n incompleta. Revisar el tÃ­tulo; no se publica un conjunto parcial.'))
                result = {'review': True}
            return {**result, 'queue': self.summary(), 'discovery_review': discovery_review}


class CachedTransport(PacedTransport):
    """Cache both providers so long anime imports progress across short cron calls."""
    def get(self, url, **kwargs):
        # Never persist API credentials or URLs containing them in a log/cache key.
        key = hashlib.sha256(json.dumps([url, kwargs.get('params', {})], sort_keys=True).encode()).hexdigest()
        cached = self.queue.cached(key)
        if cached is not None:
            from types import SimpleNamespace
            return SimpleNamespace(status_code=200, json=lambda: cached, headers={})
        remaining = self.deadline-self.clock()-max(0, self.queue.get_setting('next_request')-self.clock())
        if remaining < 3: raise BatchPause()
        kwargs['timeout'] = (min(4, remaining/2), min(8, remaining/2))
        response = super().get(url, **kwargs)
        if response.status_code == 200:
            self.queue.save_cache(key, response.json())
        return response


def run_production_batch(queue, database, vimeus_key, tmdb_key):
    if not vimeus_key or not tmdb_key:
        raise ImportFailure('Faltan las claves de importaciÃ³n.')
    transport = CachedTransport(queue, seconds=1.5, max_seconds=18)
    provider, tmdb = VimeusClient(vimeus_key, transport), TMDBClient(tmdb_key, transport)
    def publish(doc):
        database.rpc('importar_catalogo_automatico', {'documento': doc}).execute()
    return queue.run(provider, tmdb.get, publish)
