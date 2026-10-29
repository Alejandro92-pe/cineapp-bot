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
