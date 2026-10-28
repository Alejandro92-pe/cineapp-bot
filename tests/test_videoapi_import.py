import copy
import json
import pytest
from types import SimpleNamespace
from sqlalchemy import select
from providers.videoapi_catalog import VideoAPICatalog
from providers.vimeus import ImportFailure
from services.videoapi_jobs import VideoAPIQueue, jobs
from services.catalog_queue import BatchPause
from services.catalog_jobs import DurableQueue
from services.local_videoapi import apply_local


def metadata(path, params=None):
    if '/videos' in path: return {'results': []}
    if '/season/' in path:
        return {'season_number':1,'name':'Temporada 1','episodes':[
            {'season_number':1,'episode_number':n,'name':f'Capítulo {n}'} for n in range(1,4)]}
    return {'id':22,'name':'Historia','title':'Historia','seasons':[{'season_number':1}], 'vote_average':8.1}


class Provider:
    def __init__(self): self.calls=[]; self.limit=100
    def page(self, resource, page): return [{'tmdb_id':22,'title':'Historia'}], {'has_next':False}
    def exists(self, kind, tmdb, season=None, episode=None):
        if len(self.calls)>=self.limit: raise BatchPause()
        self.calls.append((kind,tmdb,season,episode)); return episode!=2


def test_rotation_resumes_across_processes_and_keeps_vimeus_queue_isolated(system):
    provider=Provider(); now=[1000]; published=[]
    for i in range(3):
        q=VideoAPIQueue(system.security_store,clock=lambda:now[0])
        result=q.run(provider,metadata,published.append)
        assert result['imported']==1
        now[0]+=100
    assert [d['contenido']['tipo'] for d in published]==['pelicula','serie','anime']
    assert DurableQueue(system.security_store).summary()=={}
    assert [e['numero'] for e in published[1]['temporadas'][0]['capitulos']]==[1,3]
    assert q.summary()=={'done':3}


def test_checkpoint_survives_pause_even_when_http_cache_expires(system):
    q=VideoAPIQueue(system.security_store,clock=lambda:1000)
    p=Provider();q.discover(p,'animes');p.limit=1;published=[]
    assert q.run(p,metadata,published.append,discover=False)['paused']
    assert not published
    q=VideoAPIQueue(system.security_store,clock=lambda:1000000)
    p.limit=100
    assert q.run(p,metadata,published.append,discover=False)['imported']==1
    assert [r[-1] for r in p.calls]==[1,2,3]
    with q.engine.connect() as c:
        progress=json.loads(c.execute(select(jobs.c.source)).scalar_one())['progress']
    assert progress['checked']==3


def test_additive_reimport_preserves_ids_links_and_cross_category_identity(system):
    db=system.supabase_service
    db.rows['contenido'][0].update(tipo='serie',tmdb_id=22,fuente='okru',playback_url='https://ok.ru/video/123')
    db.rows['temporadas']=[{'id':10,'contenido_id':1,'numero':1,'enlace':'https://mediafire.com/season'}]
    db.rows['episodios']=[{'id':20,'temporada_id':10,'numero':1,'disponible':True,
        'titulo':'Manual','descarga':'https://mediafire.com/one','provider_download_url':'https://vimeus.com/d/old',
        'vimeus_id':999,'playback_url':'https://ok.ru/video/456'},
        {'id':21,'temporada_id':10,'numero':99,'disponible':True,'descarga':'https://mediafire.com/extra'}]
    before=copy.deepcopy(db.rows)
    q=VideoAPIQueue(system.security_store);q.discover(Provider(),'animes')
    with q.engine.connect() as c:row=dict(c.execute(select(jobs)).mappings().one())
    doc,_=q.manifest(Provider(),row,metadata)
    a=apply_local(db,doc);b=apply_local(db,doc)
    assert a['contenido_id']==b['contenido_id']==1
    assert len(db.rows['contenido'])==1 and len(db.rows['episodios'])==3
    for key in ('descarga','fuente','playback_url'):
        assert db.rows['contenido'][0][key]==before['contenido'][0][key]
    for key in ('descarga','provider_download_url','vimeus_id','playback_url','id'):
        assert db.rows['episodios'][0][key]==before['episodios'][0][key]
    assert db.rows['episodios'][1]==before['episodios'][1]


@pytest.mark.parametrize('payload',[{'exists':True,'path':'https://evil.test'}, {'exists':'false'}, {}])
def test_unconfirmed_existence_never_skips_episode(payload):
    transport=SimpleNamespace(get=lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:payload))
    with pytest.raises(ImportFailure): VideoAPICatalog(transport).exists('anime',22,1,1)


def test_provider_http_failure_is_not_missing_content():
    transport=SimpleNamespace(get=lambda *a,**kw:SimpleNamespace(status_code=503))
    with pytest.raises(ImportFailure): VideoAPICatalog(transport).exists('anime',22,1,1)


def test_catalog_page_validation_never_advances_on_bad_page(system):
    payload={'status':'ok','items':[{'tmdb_id':22,'type':'movie'}], 'pagination':{'page':1,'has_next':True}}
    transport=SimpleNamespace(get=lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:payload))
    q=VideoAPIQueue(system.security_store)
    with pytest.raises(ImportFailure):q.discover(VideoAPICatalog(transport),'series')
    assert q.get_setting('page:series')==0 and q.summary()=={}


def test_scheduler_advances_after_vimeus_failure_and_keeps_batches_bounded(system, monkeypatch):
    from services import catalog_scheduler as scheduler
    q=DurableQueue(system.security_store,clock=lambda:1000);calls=[]
    monkeypatch.setattr(scheduler,'run_videoapi_batch',lambda *a:calls.append('videoapi') or {'imported':1})
    def broken(*a):calls.append('vimeus');raise RuntimeError('unavailable')
    monkeypatch.setattr(scheduler,'run_production_batch',broken)
    args=dict(videoapi_enabled=True,vimeus_key='test',tmdb_key='test')
    assert scheduler.run_batch(q,system.security_store,None,**args)['provider']=='videoapi'
    assert scheduler.run_batch(q,system.security_store,None,**args)=={'waiting':True}
    q.clock=lambda:1100
    with pytest.raises(RuntimeError):scheduler.run_batch(q,system.security_store,None,**args)
    q.clock=lambda:1200
    assert scheduler.run_batch(q,system.security_store,None,**args)['provider']=='videoapi'
    assert calls==['videoapi','vimeus','videoapi']


def test_completed_series_are_rechecked_weekly_without_duplication(system):
    q=VideoAPIQueue(system.security_store,clock=lambda:1000);p=Provider();published=[]
    q.discover(p,'series');q.run(p,metadata,published.append,discover=False)
    q.clock=lambda:1000+604801
    q.discover(p,'series')
    assert q.summary()=={'pending':1}
    q.run(p,metadata,published.append,discover=False)
    assert q.summary()=={'done':1} and len(published)==2
