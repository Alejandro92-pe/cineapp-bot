"""Vimeus is down: the automatic importer gives its turn to VideoAPI and the admin import
of a series/anime falls back to VideoAPI instead of stopping."""
import json
import pytest
from sqlalchemy import select
from providers.vimeus import ImportFailure
from services.catalog_jobs import DurableQueue
from services.catalog_queue import BatchPause
from services.videoapi_jobs import VideoAPIQueue, jobs, import_now
from test_videoapi_import import metadata, Provider


def test_vimeus_turn_goes_to_videoapi_while_vimeus_is_down(system, monkeypatch):
    from services import catalog_scheduler as scheduler
    q = DurableQueue(system.security_store, clock=lambda: 900); calls = []
    monkeypatch.setattr(scheduler, 'run_videoapi_batch', lambda *a: calls.append('videoapi') or {'imported': 1})
    monkeypatch.setattr(scheduler, 'run_production_batch', lambda *a: calls.append('vimeus') or {'imported': 1})
    args = dict(videoapi_enabled=True, vimeus_key='test', tmdb_key='test', vimeus_alive=lambda: False)
    for n in range(10):
        q.clock = lambda n=n: 900 + n * 300
        assert scheduler.run_batch(q, system.security_store, None, **args)['provider'] == 'videoapi'
    assert calls == ['videoapi'] * 10


class Published:
    def __init__(self): self.docs = []
    def rpc(self, name, params):
        assert name == 'importar_videoapi'
        self.docs.append(params['documento'])
        doc = params['documento']
        return type('R', (), {'execute': lambda s: type('D', (), {'data': {'success': True, 'contenido_id': 7,
            'titulo': doc['contenido']['titulo'], 'temporadas': len(doc['temporadas']),
            'episodios': sum(len(t['capitulos']) for t in doc['temporadas']), 'provider': 'videoapi'}})()})()


def patch_clients(monkeypatch, provider):
    import services.videoapi_jobs as module
    monkeypatch.setattr(module, 'VideoAPICatalog', lambda transport: provider)
    monkeypatch.setattr(module, 'TMDBClient', lambda key, transport: type('T', (), {'get': staticmethod(metadata)})())


def test_import_now_publishes_only_confirmed_chapters_and_keeps_queue_consistent(system, monkeypatch):
    provider = Provider(); patch_clients(monkeypatch, provider); db = Published()
    result = import_now(system.security_store, db, 'key', 'serie', 22)
    assert result['success'] and result['episodios'] == 2 and result['temporadas'] == 1   # chapter 2 is not in VideoAPI
    assert [e['numero'] for e in db.docs[0]['temporadas'][0]['capitulos']] == [1, 3]
    with system.security_store.engine.connect() as c:
        row = c.execute(select(jobs).where(jobs.c.kind == 'serie', jobs.c.tmdb == 22)).mappings().one()
    assert row['status'] == 'done'


def test_long_series_pauses_saves_progress_and_continues(system, monkeypatch):
    provider = Provider(); provider.limit = 1; patch_clients(monkeypatch, provider); db = Published()
    first = import_now(system.security_store, db, 'key', 'serie', 22)
    assert first['pending'] and first['checked'] == 1 and db.docs == []
    with system.security_store.engine.connect() as c:
        row = c.execute(select(jobs).where(jobs.c.kind == 'serie', jobs.c.tmdb == 22)).mappings().one()
    assert row['status'] == 'pending' and row['created_at'] == 0.0      # first in line for the automatic importer
    provider.limit = 100
    done = import_now(system.security_store, db, 'key', 'serie', 22)
    assert done['success'] and provider.calls.count(('serie', 22, 1, 1)) == 1   # never re-checks a saved chapter


def test_admin_import_falls_back_to_videoapi(monkeypatch):
    import routes.catalog_import as routes
    calls = []
    def failing_vimeus(*a, **k): raise ImportFailure('Vimeus no encontró este listado. No se guardaron cambios.')
    monkeypatch.setattr(routes, 'import_title', failing_vimeus)
    from flask import Flask
    app = Flask('t'); app.config['SECURITY_LOCAL'] = False
    def videoapi(kind, tmdb):
        calls.append((kind, tmdb)); return {'success': True, 'contenido_id': 7, 'titulo': 'Mr. Inbetween', 'temporadas': 3, 'episodios': 26}
    app.register_blueprint(routes.catalog_import_routes(None, None, lambda *a: {}, videoapi, lambda: True))
    test = app.test_client()
    body = test.post('/api/admin/catalog/import', json={'tmdb_id': 81499, 'tipo': 'serie'})
    assert body.status_code == 200 and body.json['provider'] == 'videoapi' and 'Vimeus no encontró' in body.json['reason']
    assert calls == [('serie', 81499)]
    # Vimeus down: VideoAPI directly, Vimeus is not even tried.
    monkeypatch.setattr(routes, 'import_title', lambda *a, **k: pytest.fail('Vimeus should not be called'))
    app2 = Flask('t2'); app2.config['SECURITY_LOCAL'] = False
    pending = lambda kind, tmdb: {'pending': True, 'checked': 12, 'total': 26, 'titulo': 'Mr. Inbetween'}
    app2.register_blueprint(routes.catalog_import_routes(None, None, lambda *a: {}, pending, lambda: False))
    body = app2.test_client().post('/api/admin/catalog/import', json={'tmdb_id': 81499, 'tipo': 'serie'})
    assert body.status_code == 202 and '12 de 26' in body.json['message']
    busy = lambda kind, tmdb: {'busy': True, 'message': 'Ocupado.'}
    app3 = Flask('t3'); app3.config['SECURITY_LOCAL'] = False
    app3.register_blueprint(routes.catalog_import_routes(None, None, lambda *a: {}, busy, lambda: False))
    assert app3.test_client().post('/api/admin/catalog/import', json={'tmdb_id': 81499, 'tipo': 'serie'}).status_code == 409
