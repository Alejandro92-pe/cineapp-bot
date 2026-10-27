import json
from types import SimpleNamespace
import pytest
from services.catalog_queue import (CatalogQueue, PacedTransport, CachedMetadata,
    BatchPause, completed_manifests, worker_lock)
from services.local_vimeus import DemoVimeus, apply_local
from providers.vimeus import ImportFailure
from local_support import LocalDatabase


class Clock:
    value=1000
    def __call__(self): return self.value
    def sleep(self,seconds): self.value+=seconds


def metadata(path, params=None):
    if path.endswith('/videos'): return {'results':[]}
    return {'title':'Película de prueba','name':'Serie de prueba','episodes':[]}


def test_resume_idempotent_atomic_publication_and_limit(tmp_path):
    path=tmp_path/'queue.sqlite'
    q=CatalogQueue(path)
    assert q.discover(DemoVimeus(),'series')==1
    assert q.discover(DemoVimeus(),'animes')==1
    assert q.discover(DemoVimeus(),'series')==0
    assert completed_manifests(path)==[]
    assert len(q.run(DemoVimeus(),metadata,limit=1))==1
    assert q.summary()=={'done':1,'pending':1}
    # Crash after claiming a title, before publishing. Restart reclaims it.
    with q.db: q.db.execute("UPDATE jobs SET status='running' WHERE status='pending'")
    q.db.close()
    q=CatalogQueue(path)
    result=q.run(DemoVimeus(),metadata,limit=3)
    assert len(result)==1 and result[0]['episodes']==72
    assert q.run(DemoVimeus(),metadata)==[]
    assert len(completed_manifests(path))==2


def test_discovery_invalid_page_does_not_advance(tmp_path):
    q=CatalogQueue(tmp_path/'q.sqlite')
    broken=SimpleNamespace(page=lambda *a:([{'tmdb_id':1},{'tmdb_id':'invalid'}],{'has_next':True}))
    with pytest.raises(ImportFailure):q.discover(broken,'movies')
    assert q.summary()=={} and not q.db.execute('SELECT * FROM cursors').fetchall()


def test_pacing_retry_after_survives_restart_and_deadline(tmp_path):
    clock=Clock();q=CatalogQueue(tmp_path/'q.sqlite',clock)
    calls=[]
    def get(*a,**kw):
        calls.append(clock())
        return SimpleNamespace(status_code=200,headers={})
    session=SimpleNamespace(get=get)
    t=PacedTransport(q,seconds=2,session=session,clock=clock,sleep=clock.sleep)
    t.get('provider');t.get('tmdb')
    assert calls==[1000,1002]
    session.get=lambda *a,**kw:SimpleNamespace(status_code=429,headers={'Retry-After':'120'})
    with pytest.raises(BatchPause):t.get('provider')
    assert q.get_setting('next_request')==1124
    q.db.close();q=CatalogQueue(tmp_path/'q.sqlite',clock)
    t=PacedTransport(q,max_seconds=30,session=session,clock=clock,sleep=clock.sleep)
    with pytest.raises(BatchPause):t.get('tmdb')
    assert t.requests==0


def test_pause_cannot_be_swallowed_by_metadata_fallback(tmp_path):
    q=CatalogQueue(tmp_path/'q.sqlite');q.discover(DemoVimeus(),'series')
    def pause(*args,**kw): raise BatchPause()
    assert q.run(DemoVimeus(),pause)==[]
    assert q.summary()=={'pending':1}
    assert completed_manifests(q.path)==[]


def test_cache_no_keys_and_reused_after_restart(tmp_path):
    clock=Clock();q=CatalogQueue(tmp_path/'q.sqlite',clock);calls=[]
    client=SimpleNamespace(get=lambda *args:(calls.append(args) or {'title':'Cached'}))
    assert CachedMetadata(q,client).get('/movie/1')['title']=='Cached'
    q.db.close();q=CatalogQueue(tmp_path/'q.sqlite',clock)
    CachedMetadata(q,client).get('/movie/1')
    assert len(calls)==1
    clock.value+=86401;CachedMetadata(q,client).get('/movie/1')
    assert len(calls)==2


def test_failed_jobs_back_off_and_stop_after_three_attempts(tmp_path):
    clock=Clock();q=CatalogQueue(tmp_path/'q.sqlite',clock);q.discover(DemoVimeus(),'series')
    provider=SimpleNamespace(episodes=lambda *a:(_ for _ in ()).throw(ImportFailure('Sin capítulos.')))
    for n in range(3):
        assert len(q.run(provider,metadata))==1
        assert q.run(provider,metadata)==[]
        clock.value+=10000
    assert q.summary()=={'failed':1} and completed_manifests(q.path)==[]


def test_movie_and_episode_manual_downloads_survive_reimport(tmp_path):
    q=CatalogQueue(tmp_path/'q.sqlite')
    provider=SimpleNamespace(page=lambda *a:([{'tmdb_id':1,'title':'Movie'}],{'has_next':False}))
    q.discover(provider,'movies');q.discover(DemoVimeus(),'animes')
    q.run(DemoVimeus(),metadata)
    db=LocalDatabase();original=db.rows['contenido'][0]['descarga']
    docs=completed_manifests(q.path)
    for document in docs:apply_local(db,document)
    episode=db.rows['episodios'][0]
    episode['descarga']='https://www.mediafire.com/file/manual/episode/file'
    manual=episode['descarga'];eid=episode['id']
    for document in docs:apply_local(db,document)
    assert db.rows['contenido'][0]['descarga']==original
    assert next(e for e in db.rows['episodios'] if e['id']==eid)['descarga']==manual
    assert len(db.rows['contenido'])==2 and len(db.rows['episodios'])==72


def test_worker_lock_rejects_second_worker_and_releases(tmp_path):
    path=tmp_path/'queue.lock'
    with worker_lock(path):
        with pytest.raises(ImportFailure):
            with worker_lock(path):pass
    with worker_lock(path):pass


def test_cli_consecutive_batches_pause_and_keep_checkpoint(tmp_path,monkeypatch):
    from scripts import import_catalog_batches as cli
    local=tmp_path/'.local';local.mkdir()
    (local/'telegram-preview.json').write_text(json.dumps({'VIMEUS_API_KEY':'fake','TMDB_API_KEY':'fake'}))
    sleeps=[]
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    monkeypatch.setattr(cli.sys,'argv',['import','--batches','2','--discover','series'])
    monkeypatch.setattr(cli.time,'sleep',sleeps.append)
    monkeypatch.setattr(cli,'VimeusClient',lambda *a:DemoVimeus())
    monkeypatch.setattr(cli,'TMDBClient',lambda *a:SimpleNamespace(get=metadata))
    assert cli.main()==0
    assert sleeps==[30]
    q=CatalogQueue(local/'import-queue.sqlite')
    assert q.summary()=={'done':1}
    assert q.db.execute('SELECT page FROM cursors').fetchone()[0]==0
