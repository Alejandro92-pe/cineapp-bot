import copy
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from tv.app import create_app, TV_COOKIE, PAIR_COOKIE
from tv.store import PairingStore, challenges
from security_store import SecurityStore, digest
from security import password_hash
from local_support import LocalDatabase
from billing.schema import access
from sqlalchemy import select

ORIGIN='http://127.0.0.1:5020'

@pytest.fixture
def tv(tmp_path):
    security=SecurityStore('sqlite:///'+str(tmp_path/'tv.sqlite'),local=True)
    account=security.create_account('Ale demo','tv@example.test',password_hash('Televisor-Local-2026!'))
    with security.engine.begin() as c:c.execute(access.insert().values(account_id=account['id'],expires_at=time.time()+3600))
    db=LocalDatabase();db.rows['contenido'][0].update(tmdb_id=22)
    db.rows['contenido'].append({**db.rows['contenido'][0],'id':2,'tipo':'serie','titulo':'Serie'})
    db.rows['temporadas']=[{'id':1,'contenido_id':2,'numero':1},{'id':2,'contenido_id':2,'numero':2}]
    db.rows['episodios']=[{'id':n,'temporada_id':1,'numero':n,'titulo':f'Episodio {n}','disponible':True,'descarga':'https://private.test/file'} for n in range(1,15)]
    app=create_app(db,security);app.config['TESTING']=True
    return app,security,account,db

def post(c,path,data=None,csrf=None):return c.post('/tv/api/'+path,json=data or {},base_url=ORIGIN,headers={'Origin':ORIGIN,**({'X-CSRF-Token':csrf} if csrf else {})})
def get(c,path):return c.get('/tv/api/'+path,base_url=ORIGIN)
def phone(c):return post(c,'phone/login',{'email':'tv@example.test','password':'Televisor-Local-2026!'}).json['csrf']
def linked(app):
    screen,cell=app.test_client(),app.test_client();p=post(screen,'pair/start').json;csrf=phone(cell)
    assert post(cell,'phone/confirm',{'code':p['code']},csrf).status_code==200
    assert post(screen,'pair/poll').json['state']=='linked'
    return screen,cell,get(screen,'me').json['csrf']

def test_pairing_requires_phone_session_csrf_and_device_secret(tv):
    app,_,_,_=tv;screen,cell,other=app.test_client(),app.test_client(),app.test_client()
    p=post(screen,'pair/start');assert p.status_code==200
    assert 'HttpOnly' in p.headers['Set-Cookie'] and 'SameSite=Strict' in p.headers['Set-Cookie']
    assert post(cell,'phone/confirm',{'code':p.json['code']}).status_code==401
    csrf=phone(cell)
    assert post(cell,'phone/confirm',{'code':p.json['code']}).status_code==403
    assert post(cell,'phone/confirm',{'code':p.json['code']},csrf).status_code==200
    assert post(other,'pair/poll',{'code':p.json['code']}).json['state']=='expired'
    assert post(screen,'pair/poll').json['state']=='linked'
    assert get(screen,'me').json['linked'] is True
    assert post(cell,'phone/confirm',{'code':p.json['code']},csrf).status_code==400
    assert post(screen,'pair/poll').json['state']=='expired'
    assert get(screen,'phone/me').json['name'] is None

def test_atomic_claim_and_expiry(tv):
    app,security,account,_=tv;clock=[1000];store=PairingStore(security,lambda:clock[0])
    token,code,_=store.start();assert store.approve(code,account['id'])
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:store.poll(token),range(2)))
    assert sorted(x[0] for x in results)==['expired','linked']
    token,code,_=store.start();clock[0]+=601
    assert store.approve(code,account['id']) is False
    assert store.poll(token)==('expired',None)

def test_pending_secrets_hashed_and_replacement_invalidates_previous(tv):
    _,security,_,_=tv;p=PairingStore(security);token,code,_=p.start()
    with security.engine.connect() as c:row=c.execute(select(challenges)).mappings().one()
    assert row['device_hash']==digest(token) and token not in str(dict(row))
    p.start(token);assert p.poll(token)[0]=='expired'

def test_membership_is_rechecked_and_phone_can_revoke_tv(tv):
    app,security,account,_=tv;c,cell,csrf=linked(app)
    assert post(c,'play',{'id':1},csrf).json['provider']=='videoapi'
    assert post(c,'play',{'id':1}).status_code==403
    with security.engine.begin() as con:con.execute(access.update().where(access.c.account_id==account['id']).values(expires_at=0))
    assert post(c,'play',{'id':1},csrf).status_code==403
    assert post(cell,'phone/revoke',{},get(cell,'phone/me').json['csrf']).status_code==200
    assert get(c,'me').json['linked'] is False
    assert post(c,'play',{'id':1},csrf).status_code==401

def test_catalog_is_bounded_readonly_and_has_no_download_fields(tv):
    app,_,_,db=tv;c=app.test_client();before=copy.deepcopy(db.rows)
    data=get(c,'episodes/2/1').json;assert len(data['items'])==6 and data['total']==14 and data['has_next']
    assert get(c,'episodes/2/1?page=3').json['has_next'] is False
    assert get(c,'episodes/1/1').status_code==404
    assert get(c,'episodes/2/1?page=0').status_code==400
    for path in ('home','title/1','episodes/2/1'):
        text=get(c,path).get_data(as_text=True)
        assert '"descarga"' not in text and 'private.test' not in text and 'has_download' not in text
    assert db.rows==before
    for route in ('/api/download/1','/api/admin/payments','/membresia'):
        assert c.get(route,base_url=ORIGIN).status_code==404

def test_episode_ownership_and_unlink(tv):
    app,_,_,_=tv;c,_,csrf=linked(app)
    assert post(c,'play',{'id':2,'episode':1},csrf).json['url'].split('?')[0].endswith('/tv/22/1/1')
    assert post(c,'play',{'id':1,'episode':1},csrf).status_code==404
    assert post(c,'play',{'id':2,'episode':999},csrf).status_code==404
    assert post(c,'unlink',{},csrf).status_code==200
    assert get(c,'me').json['linked'] is False

def test_host_origin_and_rate_limits(tv):
    app,_,_,_=tv;c=app.test_client()
    assert c.get('/tv',base_url='http://evil.test').status_code==403
    assert c.post('/tv/api/pair/start',json={},base_url=ORIGIN,headers={'Origin':'https://evil.test'}).status_code==403
    for _ in range(10):assert post(c,'pair/start').status_code==200
    assert post(c,'pair/start').status_code==429

def test_cannot_start_in_production(tv):
    _,security,_,db=tv;security.local=False
    with pytest.raises(RuntimeError):create_app(db,security,'https://app.quehay.live')


def test_next_episode_uses_numeric_order_and_crosses_seasons(tv):
    app,_,_,db=tv;catalog=app.extensions['tv_catalog']
    assert catalog.next_episode(2,9)['numero']==10
    db.rows['episodios'].append({'id':15,'temporada_id':2,'numero':1,'disponible':True})
    assert catalog.next_episode(2,14)=={'id':15,'numero':1,'titulo':None,'season':2}
    assert catalog.next_episode(1,14) is None
    assert catalog.next_episode(2,15) is None


def test_tv_top10_movies_filters_and_preserves_weekly_order(tv):
    from services.popularity import Popularity
    app, security, account, db = tv
    seed = db.rows['contenido'][0]
    db.rows['contenido'] += [{**seed, 'id': n, 'titulo': f'Película {n}'} for n in range(3, 16)]
    db.rows['contenido'].append({**seed, 'id': 16, 'disponible': False})
    client = app.test_client()
    discovery = get(client, 'home').json['top10']
    assert discovery['mode'] == 'discovery'
    assert len(discovery['items']) == 10
    assert all(r['tipo'] == 'pelicula' and r['id'] != 16 for r in discovery['items'])
    popularity = Popularity(security)
    for cid in (2, 5, 3, 16):
        popularity.record(account['id'], cid)
    other = security.create_account('Otro', 'otro@example.test', password_hash('Otra-Clave-2026!'))
    popularity.record(other['id'], 5)
    ranked = get(client, 'home').json['top10']
    assert ranked['mode'] == 'ranked'
    assert [r['id'] for r in ranked['items']] == [5, 3]
    assert all('descarga' not in row for row in ranked['items'])


def test_tv_detail_reports_real_episode_and_missing_state(tv):
    app, _, _, db = tv
    c = app.test_client()
    movie = get(c, 'title/1').json
    assert movie['playable'] and not movie['episodic'] and movie['first_episode'] is None
    series = get(c, 'title/2').json
    assert series['episodic'] and series['first_episode']['numero'] == 1
    assert series['first_episode']['season'] == 1 and series['playable']
    assert 'descarga' not in series['first_episode']
    db.rows['episodios'] = []
    missing = get(c, 'title/2').json
    assert missing['episodic'] and not missing['playable'] and missing['first_episode'] is None
    assert get(c, 'title/99999').status_code == 404


def test_tv_snapshot_deduplicates_and_excludes_private_fields(tmp_path):
    import json
    from tv.snapshot import prepare
    (tmp_path/'videoapi-production').mkdir()
    (tmp_path/'visual-refresh').mkdir()
    (tmp_path/'vimeus-manifests').mkdir()
    title={'id':10,'titulo':'Serie','tipo':'serie','tmdb_id':20,'disponible':True}
    backup={'public.contenido':[dict(title,descarga='SECRET')],
        'public.temporadas':[{'id':22,'contenido_id':10,'numero':1,'enlace':'SECRET'}, {'id':23,'contenido_id':10,'numero':1}],
        'public.episodios':[{'id':1,'temporada_id':22,'numero':1,'titulo':'Uno','descarga':'SECRET','disponible':True}, {'id':2,'temporada_id':23,'numero':1,'titulo':'Uno','disponible':True}],
        'cine_security.accounts':[{'password_hash':'SECRET'}]}
    (tmp_path/'videoapi-production/backup-private.json').write_text(json.dumps(backup),encoding='utf8')
    (tmp_path/'visual-refresh/catalog-all.json').write_text(json.dumps([title]),encoding='utf8')
    manifest={'contenido':title,'temporadas':[{'numero':1,'capitulos':[{'numero':1,'titulo':'Otro'}, {'numero':2,'titulo':'Dos','provider_download_url':'SECRET'}]}]}
    (tmp_path/'vimeus-manifests/serie-20.json').write_text(json.dumps(manifest),encoding='utf8')
    data, report=prepare(tmp_path)
    assert len(data['temporadas']) == 1 and len(data['episodios']) == 2
    assert data['temporadas'][0]['episodios'] == 2
    assert 'SECRET' not in json.dumps(data) and 'accounts' not in data
    assert data['episodios'][0]['titulo'] == 'Uno'
    assert report['public_gets'] == 0 and not report['missing']


def test_collection_filters_full_catalog_and_preserves_category(tv):
    app, _, _, db = tv
    seed = db.rows['contenido'][0]
    db.rows['contenido'] = [{**seed,'id':n,'titulo':f'Drama {n}','genero':'Drama','rating':n/10} for n in range(1,22)]
    db.rows['contenido'] += [{**seed,'id':23,'titulo':'Último terror','genero':'Terror, Suspense','rating':9},
        {**seed,'id':24,'titulo':'Oculta','genero':'Terror','disponible':False},
        {**seed,'id':25,'titulo':'Anime','genero':'Action & Adventure, Sci-Fi & Fantasy','tipo':'anime'}]
    c=app.test_client()
    result=get(c,'catalog?kind=pelicula&genre=drama&sort=az&page=2').json
    assert result['total']==21 and len(result['items'])==9 and not result['has_next']
    result=get(c,'catalog?kind=pelicula&genre=suspenso&q=ultimo').json
    assert result['total']==1 and result['items'][0]['id']==23
    assert result['featured']['id']==23
    genres={x['id']:x['count'] for x in result['genres']}
    assert genres['terror']==1 and genres['drama']==21
    result=get(c,'catalog?kind=pelicula&sort=rating').json
    assert result['items'][0]['id']==23
    anime=get(c,'catalog?kind=anime&genre=aventura').json
    assert anime['total']==1 and anime['items'][0]['id']==25
    assert get(c,'catalog?kind=pelicula&genre=drama&q=no-existe').json['total']==0
    for query in ('genre=inventado','sort=unknown','kind=serie&format=movies'):
        assert get(c,'catalog?'+query).status_code==400


def test_biblical_formats_and_metadata_cache(tv):
    from tv.discovery import Discovery
    _, _, _, db=tv
    db.rows['contenido'][0]['tipo']='biblico'
    db.rows['contenido'][1]['tipo']='biblico'
    clock=[10];discovery=Discovery(db,lambda:clock[0])
    serial=discovery.browse('biblico',form='series')
    assert [x['id'] for x in serial['items']]==[2]
    assert serial['items'][0]['format']=='series'
    assert discovery.browse('biblico',form='movies')['items'][0]['id']==1
    db.rows['contenido'].append({**db.rows['contenido'][0],'id':3})
    assert discovery.browse('biblico')['total']==2
    clock[0]=311
    assert discovery.browse('biblico')['total']==3
    assert '_genres' not in str(serial) and 'descarga' not in serial['items'][0]


def test_tv_saved_list_requires_session_csrf_and_stays_private(tv):
    from services.profiles import Profiles
    app,security,account,db=tv
    anonymous=app.test_client()
    assert get(anonymous,'list').status_code==401
    assert post(anonymous,'list',{'id':1,'saved':True}).status_code==401
    c,cell,csrf=linked(app)
    assert post(c,'list',{'id':1,'saved':True}).status_code==403
    for data in ({'id':True,'saved':True},{'id':1,'saved':'true'},{'id':-1,'saved':True}):
        assert post(c,'list',data,csrf).status_code==400
    assert post(c,'list',{'id':999,'saved':True},csrf).status_code==404
    before=copy.deepcopy(db.rows)
    assert post(c,'list',{'id':1,'saved':True},csrf).status_code==200
    assert post(c,'list',{'id':1,'saved':True},csrf).status_code==200
    result=get(c,'list').json
    assert result['total']==1 and result['items'][0]['id']==1
    assert all('descarga' not in row for row in result['items']) and 'private.test' not in str(result)
    assert get(c,'title/1').json['saved'] is True
    assert get(anonymous,'title/1').json['saved'] is False
    # Same account on another paired device sees persisted entries.
    second,_,second_csrf=linked(app)
    assert get(second,'list').json['total']==1
    other=security.create_account('Other','other@example.test',password_hash('Other-Test-2026!'))
    token,code=app.extensions['tv_pairing'].start()[:2]
    app.extensions['tv_pairing'].approve(code,other['id'])
    _,device=app.extensions['tv_pairing'].poll(token)
    outsider=app.test_client();outsider.set_cookie(TV_COOKIE,device,domain='127.0.0.1',path='/tv')
    assert get(outsider,'list').json['total']==0
    with security.engine.begin() as con:con.execute(access.update().where(access.c.account_id==account['id']).values(expires_at=0))
    assert post(second,'list',{'id':2,'saved':True},second_csrf).status_code==200
    assert post(second,'play',{'id':2,'episode':1},second_csrf).status_code==403
    assert post(c,'list',{'id':1,'saved':False},csrf).status_code==200
    assert Profiles(security).snapshot(account['id'])['saved_ids']==[2]
    assert get(second,'title/1').json['saved'] is False
    assert db.rows==before
    assert post(cell,'phone/revoke',{},get(cell,'phone/me').json['csrf']).status_code==200
    assert get(second,'list').status_code==401


def test_saved_list_pages_and_unavailable_entries(tv):
    from services.profiles import Profiles
    app,security,account,db=tv
    seed=db.rows['contenido'][0]
    db.rows['contenido']=[{**seed,'id':n,'disponible':n!=14} for n in range(1,15)]
    Profiles(security).mutate(account['id'],items=[(n,True) for n in range(1,15)])
    c,_,csrf=linked(app)
    first=get(c,'list').json;last=get(c,'list?page=2').json
    assert first['total']==13 and len(first['items'])==12 and first['has_next']
    assert len(last['items'])==1 and not last['has_next']
    assert get(c,'list?page=0').status_code==400
    assert post(c,'list',{'id':14,'saved':False},csrf).status_code==200
