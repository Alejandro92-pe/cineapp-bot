import copy
from types import SimpleNamespace
from services.artwork import ArtworkMaintenance, SNAPSHOT, metadata_for
from services.hero import PERIOD
from conftest import send


def service(system,tmdb=None):
    return ArtworkMaintenance(system.catalog_job_store,system.supabase_service,tmdb)


def test_repairs_only_backdrop_and_keeps_accounts_downloads_and_identity(system):
    before=copy.deepcopy(system.supabase_service.rows)
    tmdb=SimpleNamespace(get=lambda p:{'id':1,'backdrop_path':'/wide.jpg'})
    result=service(system,tmdb).repair_one()
    assert result['updated'] is True
    after=copy.deepcopy(system.supabase_service.rows)
    assert after['contenido'][0].pop('backdrop_url')=='https://image.tmdb.org/t/p/w1280/wide.jpg'
    assert after==before


def test_does_not_replace_existing_manual_background_or_mismatched_tmdb(system):
    row=system.supabase_service.rows['contenido'][0];row['backdrop_url']='https://example.org/handpicked.jpg'
    def fail(*a):raise AssertionError('Should not fetch existing artwork')
    assert not service(system,SimpleNamespace(get=fail)).repair_one()['updated']
    row.pop('backdrop_url');system.catalog_job_store.set_setting('visual:cursor',0)
    import pytest
    with pytest.raises(ValueError):service(system,SimpleNamespace(get=lambda p:{'id':2,'backdrop_path':'/wrong.jpg'})).repair_one()
    assert 'backdrop_url' not in row


def test_legacy_matching_requires_unique_exact_title_and_year():
    row={'tipo':'pelicula','titulo':'El Padrino','año':1972}
    meta={'id':238,'title':'El padrino','original_title':'The Godfather','release_date':'1972-03-14','backdrop_path':'/wide.jpg'}
    api=SimpleNamespace(search_movie=lambda *a:{'results':[meta]})
    assert metadata_for(row,api)==meta
    assert metadata_for(row,SimpleNamespace(search_movie=lambda *a:{'results':[meta,meta]}))=={}
    assert metadata_for({**row,'año':2026},api)=={}


def test_legacy_series_and_alternate_title_require_year_or_exact_poster():
    row={'tipo':'serie','titulo':'Una serie','año':2020}
    meta={'id':8,'name':'Una serie','first_air_date':'2020-04-01','backdrop_path':'/wide.jpg'}
    assert metadata_for(row,SimpleNamespace(search_title=lambda *a:{'results':[meta]}))==meta
    film={'tipo':'pelicula','titulo':'Título editorial','año':2020,'imagen_url':'https://media.themoviedb.org/t/p/w300_and_h450_face/p.jpg'}
    alternate={'title':'Otro título','release_date':'2020-01-01','poster_path':'/p.jpg'}
    assert metadata_for(film,SimpleNamespace(search_movie=lambda *a:{'results':[alternate]}))==alternate
    assert metadata_for({**film,'año':2021},SimpleNamespace(search_movie=lambda *a:{'results':[alternate]}))=={}


def test_biblical_id_without_media_cannot_take_image_from_wrong_namespace():
    row={'tipo':'biblico','titulo':'Historia bíblica','año':2020,'tmdb_id':8}
    unrelated={'id':8,'title':'Otro título','release_date':'2020-01-01','backdrop_path':'/wrong.jpg'}
    assert metadata_for(row,SimpleNamespace(get=lambda *a:unrelated))=={}


def pool(system):
    now=1793236204
    system.catalog_job_store.clock=lambda:now
    system.supabase_service.rows['contenido']=[{'id':i,'tmdb_id':100+i,'titulo':f'Título {i}','tipo':'pelicula','año':2026,
        'disponible':True,'descarga':'https://private.example/file','enlace_canal':'secret'} for i in range(1,10)]
    results=[{'id':100+i,'title':f'Título {i}','release_date':'2026-01-02','vote_average':8,'vote_count':500,'adult':False,
              'poster_path':f'/poster{i}.jpg','backdrop_path':f'/wide{i}.jpg'} for i in range(1,10)]
    return now,results


def test_rotation_persistent_three_days_deduplicated_and_available_only(system):
    now,rows=pool(system)
    rows.extend([rows[0],{**rows[0],'id':555},{**rows[1],'id':999,'adult':True}])
    calls=[]
    api=SimpleNamespace(discover_movies=lambda y,p:(calls.append((y,p)) or {'results':rows,'total_pages':1}))
    s=service(system,api)
    assert s.discover_step()=={'published':3}
    first=s.public();assert len(first['items'])==3
    s.discover_step();assert len(calls)==1
    assert service(system).public()==first
    assert all(set(r)=={'id','tmdb_id','title','year','rating','poster','backdrop'} for r in first['items'])
    system.catalog_job_store.clock=lambda:now+PERIOD
    assert s.discover_step()=={'published':3}
    second=s.public();assert not {r['id'] for r in first['items']}&{r['id'] for r in second['items']}
    selected=second['items'][0]['id']
    next(r for r in system.supabase_service.rows['contenido'] if r['id']==selected)['disponible']=False
    assert selected not in [r['id'] for r in s.public()['items']]


def test_partial_or_insufficient_discovery_keeps_last_good_selection(system):
    now,rows=pool(system);s=service(system,SimpleNamespace(discover_movies=lambda *a:{'results':rows,'total_pages':1}))
    s.discover_step();old=s.public();system.catalog_job_store.clock=lambda:now+PERIOD
    s.tmdb=SimpleNamespace(discover_movies=lambda *a:{'results':rows[:1],'total_pages':3})
    assert s.discover_step()['collecting'];assert s.public()==old
    assert s.discover_step()['collecting'];assert s.public()==old
    assert s.discover_step()['kept_previous'];assert s.public()==old


def test_public_feed_has_no_external_fetch_no_session_and_cors_only_on_feed(client,system,monkeypatch):
    now,rows=pool(system)
    service(system,SimpleNamespace(discover_movies=lambda *a:{'results':rows,'total_pages':1})).discover_step()
    def denied(*a,**kw):raise AssertionError('Public feed must not touch sessions or TMDB')
    monkeypatch.setattr(system.security_store,'session',denied)
    result=send(client,'/api/public/landing',method='GET',headers={'Origin':'https://quehay.live'})
    assert result.status_code==200 and len(result.json['items'])==3
    assert result.headers['Access-Control-Allow-Origin']=='https://quehay.live'
    assert 'Access-Control-Allow-Credentials' not in result.headers
    assert 'Set-Cookie' not in result.headers
    assert 'private.example' not in result.text and 'secret' not in result.text
    other=send(client,'/api/public/landing',method='GET',headers={'Origin':'https://evil.test'})
    assert 'Access-Control-Allow-Origin' not in other.headers


def test_cron_requires_auth_and_local_cannot_write_production(client,system):
    import os
    assert send(client,'/cron/actualizar_imagenes',method='GET').status_code==401
    response=send(client,'/cron/actualizar_imagenes',method='GET',headers={'Authorization':'Bearer '+os.environ['CRON_SECRET']})
    assert response.json=={'enabled':False}
    assert 'Access-Control-Allow-Origin' not in send(client,'/api/auth/me',method='GET',headers={'Origin':'https://quehay.live'}).headers


def test_worker_throttles_and_does_not_advance_import_cursors(system):
    now,rows=pool(system)
    q=system.catalog_job_store
    q.set_setting('provider_turn',7);q.set_setting('work_turn',2)
    api=SimpleNamespace(get=lambda p:{'id':int(p.split('/')[-1]),'backdrop_path':'/wide.jpg'},discover_movies=lambda *a:{'results':rows,'total_pages':1})
    s=service(system,api);s.run()
    assert s.run()=={'waiting':True}
    assert q.get_setting('provider_turn')==7 and q.get_setting('work_turn')==2


def test_outage_keeps_snapshot_and_can_retry(system):
    now,rows=pool(system);s=service(system,SimpleNamespace(discover_movies=lambda *a:{'results':rows,'total_pages':1}))
    s.discover_step();old=s.public();system.catalog_job_store.clock=lambda:now+PERIOD
    def down(*a):raise TimeoutError()
    s.tmdb=SimpleNamespace(get=down,discover_movies=down)
    assert s.run()['landing']['retry_later']
    assert s.public()==old


def test_reviewed_bulk_changes_preserve_downloads_and_skip_new_editor_changes(system):
    from services.artwork import apply_reviewed
    db=system.supabase_service
    rows=db.rows['contenido'];rows.append({**rows[0],'id':2,'backdrop_url':'https://example.org/editor.jpg'})
    before=copy.deepcopy(db.rows)
    changes=[{'id':r['id'],'titulo':r['titulo'],'tipo':r['tipo'],'tmdb_id':r['tmdb_id'],'previous_backdrop':None,
        'backdrop_url':'https://image.tmdb.org/t/p/w1280/correct.jpg'} for r in rows]
    assert apply_reviewed(db,changes)['eligible']==1
    assert db.rows==before
    result=apply_reviewed(db,changes,apply=True);assert result['updated']==1 and result['conflicts']==[2]
    after=copy.deepcopy(db.rows);after['contenido'][0].pop('backdrop_url');assert after==before
    assert apply_reviewed(db,changes,apply=True)['updated']==0
