"""Independent resumable queue. No Vimeus credentials or availability required."""
import copy
import json
import time
from sqlalchemy import Table, Column, String, Text, Integer, Float, select, update
from security_store import metadata
from services.catalog_jobs import DurableQueue, CachedTransport
from services.catalog_queue import movie_manifest
from providers.videoapi_catalog import VideoAPICatalog
from providers.vimeus import ImportFailure, integer
from providers.tmdb import TMDBClient, tmdb_rating, trailer_url
from services.vimeus_import import image_url

jobs = Table('videoapi_jobs', metadata,
    Column('kind', String(20), primary_key=True), Column('tmdb', Integer, primary_key=True),
    Column('source', Text, nullable=False), Column('status', String(16), nullable=False),
    Column('attempts', Integer, nullable=False), Column('ready', Float, nullable=False),
    Column('created_at', Float, nullable=False), Column('note', String(300)))


class VideoAPIQueue(DurableQueue):
    pending_states = ('pending', 'refresh_pending')
    running_states = {'running': 'pending', 'refresh_running': 'refresh_pending'}
    def __init__(self, store, clock=time.time):
        super().__init__(store, clock, job_table=jobs, namespace='videoapi:')

    def prepare_work(self):
        # Keep completed titles completed while the first pass has eligible work.
        # Admit at most one weekly refresh; paused refreshes retain their lower
        # priority and checkpoints even when new titles arrive or a worker restarts.
        with self.engine.begin() as c:
            if c.execute(select(jobs.c.tmdb).where(jobs.c.status == 'pending',
                    jobs.c.ready <= self.clock()).limit(1)).first(): return
            if c.execute(select(jobs.c.tmdb).where(jobs.c.status.in_(
                    ('refresh_pending', 'refresh_running'))).limit(1)).first(): return
            row = c.execute(select(jobs).where(jobs.c.status == 'done', jobs.c.ready <= self.clock())
                            .order_by(jobs.c.ready, jobs.c.created_at, jobs.c.tmdb).limit(1)).mappings().first()
            if row:
                source = json.loads(row['source']); source.pop('progress', None)
                c.execute(update(jobs).where(jobs.c.kind == row['kind'], jobs.c.tmdb == row['tmdb']).values(
                    status='refresh_pending', source=json.dumps(source), attempts=0, note=None))

    def manifest(self, provider, row, get):
        source = json.loads(row['source'])
        kind, tmdb = row['kind'], row['tmdb']
        if kind == 'pelicula':
            if not provider.exists(kind, tmdb):
                raise ImportFailure('La película ya no está disponible.')
            meta = get(f'/movie/{tmdb}')
            if integer(meta.get('id'), 1) != tmdb:
                raise ImportFailure('TMDB devolvió otra película.')
            doc, warnings = movie_manifest(source, lambda path, params=None:
                meta if path == f'/movie/{tmdb}' else get(path, params))
            doc['contenido'].update(tmdb_media='movie', videoapi_kind=kind)
            return doc, warnings
        progress = source.get('progress')
        dirty = False
        def mark_progress():
            nonlocal dirty
            dirty = True
        try:
            if progress is None:
                meta = get(f'/tv/{tmdb}')
                if integer(meta.get('id'), 1) != tmdb:
                    raise ImportFailure('TMDB devolvió otra serie.')
                seasons = meta.get('seasons')
                if not isinstance(seasons, list) or not 1 <= len(seasons) <= 100:
                    raise ImportFailure('Temporadas incompletas.')
                numbers = [integer(s.get('season_number')) for s in seasons]
                if len(set(numbers)) != len(numbers):
                    raise ImportFailure('Temporadas duplicadas.')
                content = {'tipo': kind, 'tmdb_id': tmdb, 'tmdb_media': 'tv', 'videoapi_kind': kind,
                    'titulo': meta.get('name') or source['title'], 'sinopsis': meta.get('overview') or '',
                    'imagen_url': image_url(meta.get('poster_path')),
                    'backdrop_url': image_url(meta.get('backdrop_path')).replace('/w500', '/w1280'),
                    'genero': ', '.join(g['name'] for g in meta.get('genres', []) if g.get('name')),
                    'rating': tmdb_rating(meta), 'trailer_url': trailer_url(get, 'tv', tmdb)}
                year = str(meta.get('first_air_date') or '')[:4]
                if year.isdigit(): content['año'] = int(year)
                progress = {'document': {'contenido': content, 'temporadas': []},
                            'seasons': sorted(numbers), 'season_index': 0, 'episode_index': 0,
                            'counts': {str(s['season_number']): integer(s['episode_count'])
                                       for s in seasons if s.get('episode_count') is not None},
                            'checked': 0, 'missing': 0, 'pending_season': None}
                mark_progress()
            while progress['season_index'] < len(progress['seasons']):
                number = progress['seasons'][progress['season_index']]
                if progress['pending_season'] is None:
                    detail = get(f'/tv/{tmdb}/season/{number}')
                    episodes = detail.get('episodes')
                    if integer(detail.get('season_number')) != number or not isinstance(episodes, list):
                        raise ImportFailure('Temporada incorrecta o incompleta.')
                    expected = progress.get('counts', {}).get(str(number))
                    if expected is not None and len(episodes) != expected:
                        raise ImportFailure('TMDB cambió o entregó una temporada parcial; requiere revisión.')
                    seen, normalized = set(), []
                    for e in episodes:
                        n = integer(e.get('episode_number'), 1)
                        if n in seen or integer(e.get('season_number')) != number:
                            raise ImportFailure('Episodio repetido o de otra temporada.')
                        seen.add(n)
                        normalized.append({'numero': n, 'titulo': e.get('name') or f'Episodio {n}',
                            'sinopsis': e.get('overview') or '', 'imagen_url': image_url(e.get('still_path')),
                            'duracion': e.get('runtime') if type(e.get('runtime')) is int and e['runtime'] > 0 else None})
                    if progress['checked'] + len(normalized) > 5000:
                        raise ImportFailure('El título supera 5.000 capítulos; requiere revisión.')
                    progress['pending_season'] = {'numero': number, 'nombre': detail.get('name') or f'Temporada {number}',
                        'descripcion': detail.get('overview') or '', 'poster_url': image_url(detail.get('poster_path')),
                        'capitulos': [], 'candidates': sorted(normalized, key=lambda e:e['numero'])}
                    mark_progress()
                season = progress['pending_season']
                while progress['episode_index'] < len(season['candidates']):
                    e = season['candidates'][progress['episode_index']]
                    if provider.exists(kind, tmdb, number, e['numero']):
                        season['capitulos'].append(e)
                    else: progress['missing'] += 1
                    progress['checked'] += 1
                    progress['episode_index'] += 1
                    mark_progress()
                season.pop('candidates')
                if season['capitulos']: progress['document']['temporadas'].append(season)
                progress.update(season_index=progress['season_index']+1, episode_index=0, pending_season=None)
                mark_progress()
            if not progress['document']['temporadas']:
                raise ImportFailure('No hay capítulos confirmados en VideoAPI.')
            warnings = [f"{progress['missing']} episodios de TMDB no disponibles en VideoAPI."] if progress['missing'] else []
            return copy.deepcopy(progress['document']), warnings
        finally:
            # Flush validated progress once, including BatchPause (BaseException).
            # Publication happens only after this commit. A hard process kill may
            # replay the current batch, but never skips an unchecked episode.
            if dirty:
                source['progress'] = progress
                with self.engine.begin() as c:
                    c.execute(update(jobs).where(jobs.c.kind == kind, jobs.c.tmdb == tmdb)
                              .values(source=json.dumps(source)))


def run_videoapi_batch(queue, database, tmdb_key):
    if not tmdb_key:
        raise ImportFailure('Falta la clave de TMDB.')
    transport = CachedTransport(queue, seconds=1.5, max_seconds=18)
    provider, tmdb = VideoAPICatalog(transport), TMDBClient(tmdb_key, transport)
    def publish(doc):
        result = database.rpc('importar_videoapi', {'documento': doc}).execute().data
        if not isinstance(result, dict) or not result.get('success'):
            raise ImportFailure('La publicación no fue confirmada.')
    return queue.run(provider, tmdb.get, publish)


def import_now(store, database, tmdb_key, kind, tmdb, seconds=20):
    """Admin import of one series/anime from VideoAPI (when Vimeus is down or lacks it).

    Runs the same validated manifest as the automatic queue for at most `seconds` (a web
    thread must never be held for minutes). A long series saves its progress and stays first
    in the queue: pressing import again, or the next automatic turn, continues where it left off.
    """
    from services.catalog_jobs import BatchPause
    if kind not in ('serie', 'anime'):
        raise ImportFailure('Solo series y animes se importan desde VideoAPI aquí.')
    if not tmdb_key:
        raise ImportFailure('Falta la clave de TMDB.')
    queue = VideoAPIQueue(store)
    with queue.lock() as acquired:
        if not acquired:
            return {'busy': True, 'message': 'El importador automático está trabajando. Vuelve a pulsar Importar en unos segundos.'}
        target = (jobs.c.kind == kind) & (jobs.c.tmdb == tmdb)
        with queue.engine.begin() as c:
            row = c.execute(select(jobs).where(target)).mappings().first()
            if row is None:
                c.execute(jobs.insert().values(kind=kind, tmdb=tmdb, source=json.dumps({'tmdb_id': tmdb, 'title': ''}),
                    status='pending', attempts=0, ready=queue.clock(), created_at=0.0, note='Importación manual'))
            elif row['status'] not in ('pending', 'refresh_pending'):
                # done/failed/running: restart from the saved progress, if any, at the front of the queue.
                c.execute(update(jobs).where(target).values(status='pending', attempts=0, ready=queue.clock(),
                    created_at=0.0, note='Importación manual'))
            else:
                c.execute(update(jobs).where(target).values(ready=queue.clock(), created_at=0.0))
            row = dict(c.execute(select(jobs).where(target)).mappings().one())
        transport = CachedTransport(queue, seconds=1.5, max_seconds=seconds)
        provider, client = VideoAPICatalog(transport), TMDBClient(tmdb_key, transport)
        try:
            doc, warnings = queue.manifest(provider, row, client.get)
        except BatchPause:
            with queue.engine.connect() as c:
                source = json.loads(c.execute(select(jobs.c.source).where(target)).scalar_one())
            progress = source.get('progress') or {}
            total = sum(progress.get('counts', {}).values()) or None
            return {'pending': True, 'provider': 'videoapi', 'checked': progress.get('checked', 0), 'total': total,
                    'titulo': (progress.get('document') or {}).get('contenido', {}).get('titulo')}
        except ImportFailure as error:
            with queue.engine.begin() as c:
                c.execute(update(jobs).where(target).values(status='failed', note=str(error)[:300], ready=queue.clock()+3600))
            raise ImportFailure(f'VideoAPI tampoco pudo importarla: {error}') from None
        result = database.rpc('importar_videoapi', {'documento': doc}).execute().data
        if not isinstance(result, dict) or not result.get('success'):
            raise ImportFailure('La publicación no fue confirmada. No se guardaron cambios.')
        with queue.engine.begin() as c:
            c.execute(update(jobs).where(target).values(status='done', attempts=0, ready=queue.clock()+604800,
                note='; '.join(warnings)[:300] or 'Importación manual'))
        return {**result, 'warnings': warnings}
