import json
from types import SimpleNamespace
from sqlalchemy import select, update, event
from services.videoapi_jobs import VideoAPIQueue, jobs
from services.catalog_jobs import DurableQueue
from services.catalog_queue import BatchPause
from test_videoapi_import import Provider, metadata


def seed(q, tmdb, kind='pelicula', status='pending', ready=0, created=1):
    with q.engine.begin() as c:
        c.execute(jobs.insert().values(kind=kind, tmdb=tmdb, status=status, ready=ready,
            source=json.dumps({'tmdb_id':tmdb,'title':'Fixture'}), attempts=0, created_at=created))


def fake_manifest(provider,row,get):
    return {'tmdb':row['tmdb']},[]


def test_new_titles_win_across_categories_before_weekly_refresh(system):
    q=VideoAPIQueue(system.security_store,clock=lambda:1000)
    seed(q,1,'pelicula','done');seed(q,2,'anime',created=100)
    q.manifest=fake_manifest;published=[]
    assert q.run(Provider(),metadata,published.append,discover=False)['tmdb_id']==2
    with q.engine.connect() as c:
        assert c.execute(select(jobs.c.status).where(jobs.c.tmdb==1)).scalar_one()=='done'
    q.clock=lambda:1300
    assert q.run(Provider(),metadata,published.append,discover=False)['tmdb_id']==1
    assert published==[{'tmdb':2},{'tmdb':1}]


def test_paused_refresh_retains_lower_priority_and_checkpoint_after_restart(system):
    q=VideoAPIQueue(system.security_store,clock=lambda:1000);p=Provider();out=[]
    q.discover(p,'animes');q.run(p,metadata,out.append,discover=False)
    q.clock=lambda:1000+604801;p.calls=[];p.limit=1
    assert q.run(p,metadata,out.append,discover=False)['paused']
    with q.engine.connect() as c:
        row=c.execute(select(jobs)).mappings().one()
        assert row['status']=='refresh_pending'
        assert json.loads(row['source'])['progress']['checked']==1
    seed(q,23,'pelicula',created=900000)
    q=VideoAPIQueue(system.security_store,clock=lambda:900000);p.limit=100
    original=q.manifest
    q.manifest=lambda provider,row,get: fake_manifest(provider,row,get) if row['tmdb']==23 else original(provider,row,get)
    assert q.run(p,metadata,out.append,discover=False)['tmdb_id']==23
    q.clock=lambda:900300
    assert q.run(p,metadata,out.append,discover=False)['tmdb_id']==22
    assert [x[-1] for x in p.calls]==[1,2,3]
    assert q.summary()=={'done':2}


def test_refresh_crash_recovery_and_bounded_admission(system):
    q=VideoAPIQueue(system.security_store,clock=lambda:1000)
    seed(q,1,status='refresh_running');seed(q,2,status='done');seed(q,3,status='done')
    def pause(*args):raise BatchPause()
    q.manifest=pause
    assert q.run(Provider(),metadata,lambda d:None,discover=False)['paused']
    with q.engine.connect() as c:
        assert dict(c.execute(select(jobs.c.tmdb,jobs.c.status)).all())=={1:'refresh_pending',2:'done',3:'done'}
    assert q.summary()=={'pending':1,'done':2}


def test_refresh_cannot_skip_backoff_and_stops_after_three_failures(system):
    now=[1000];q=VideoAPIQueue(system.security_store,clock=lambda:now[0]);seed(q,1,status='done')
    def fail(*args):raise ValueError('unavailable')
    q.manifest=fail
    for attempt in range(3):
        assert q.run(Provider(),metadata,lambda d:None,discover=False)['review']
        now[0]+=61
        if attempt<2:
            assert 'review' not in q.run(Provider(),metadata,lambda d:None,discover=False)
        now[0]+=5000
    assert q.summary()=={'failed':1}
    assert not q.run(Provider(),metadata,lambda d:None,discover=False).get('imported')


def test_discovery_is_one_insert_for_24_titles_and_idempotent(system):
    q=VideoAPIQueue(system.security_store);sql=[]
    provider=SimpleNamespace(page=lambda *a:([{'tmdb_id':i+1,'title':'Fixture'} for i in range(24)],{'has_next':True}))
    def record(c,cur,statement,params,context,many):
        if 'INSERT INTO' in statement and 'videoapi_jobs' in statement:sql.append(statement)
    event.listen(q.engine,'before_cursor_execute',record)
    try:q.discover(provider,'movies');q.discover(provider,'movies')
    finally:event.remove(q.engine,'before_cursor_execute',record)
    assert len(sql)==2 and q.summary()=={'pending':24}


def test_local_queues_share_one_worker_lock(system):
    first=VideoAPIQueue(system.security_store);second=DurableQueue(system.security_store)
    with first.lock() as acquired:
        assert acquired
        with second.lock() as competing:assert not competing
    with second.lock() as released:assert released


def test_restart_keeps_schedule_and_missing_vimeus_uses_videoapi(system,monkeypatch):
    from services import catalog_scheduler as s
    calls=[]
    monkeypatch.setattr(s,'run_videoapi_batch',lambda *a:calls.append('videoapi') or {})
    args=dict(videoapi_enabled=True,vimeus_key='',tmdb_key='test')
    q=DurableQueue(system.security_store,clock=lambda:1000);q.set_setting('provider_turn',4)
    assert s.run_batch(q,system.security_store,None,**args)['provider']=='videoapi'
    q=DurableQueue(system.security_store,clock=lambda:1299)
    assert s.run_batch(q,system.security_store,None,**args)=={'waiting':True}
    q.clock=lambda:1300
    assert s.run_batch(q,system.security_store,None,**args)['provider']=='videoapi'
    assert len(calls)==2


def test_full_day_schedule_is_four_to_one_with_no_early_requests(system,monkeypatch):
    from services import catalog_scheduler as s
    now=[1000];q=DurableQueue(system.security_store,clock=lambda:now[0]);calls=[]
    monkeypatch.setattr(s,'run_videoapi_batch',lambda *a:calls.append('videoapi') or {})
    monkeypatch.setattr(s,'run_production_batch',lambda *a:calls.append('vimeus') or {})
    args=dict(videoapi_enabled=True,vimeus_key='fixture',tmdb_key='fixture')
    for _ in range(288):
        assert s.run_batch(q,system.security_store,None,**args)['provider'] in ('videoapi','vimeus')
        now[0]+=299
        assert s.run_batch(q,system.security_store,None,**args)=={'waiting':True}
        now[0]+=1
    assert calls.count('videoapi')==231 and calls.count('vimeus')==57
