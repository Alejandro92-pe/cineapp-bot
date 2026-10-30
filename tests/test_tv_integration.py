import copy
import time
from types import SimpleNamespace
import pytest
from flask import Response
from werkzeug.test import Client
from sqlalchemy import event, select
from conftest import ORIGIN, send, register, tg_login
from tv.integration import compose, install
from tv.app import create_app, LIVE_TV_COOKIE
from tv.store import devices, challenges
from billing.schema import access
from security import COOKIE

@pytest.fixture
def integrated(system):
    router=compose(system.app,system.supabase_service,system.security_store,system.account_legacy_expiry,enabled=True)
    system.supabase_service.rows['contenido'][0].update(tmdb_id=22)
    return router,system

def client(router):return Client(router,Response)
def get(c,path):return c.get(path,base_url=ORIGIN)
def post(c,path,body=None,csrf=None):return send(c,path,body or {},csrf)
def grant(system,account_id,expiry):
    with system.security_store.engine.begin() as c:
        c.execute(access.delete().where(access.c.account_id==account_id))
        c.execute(access.insert().values(account_id=account_id,expires_at=expiry))
def pair(tv,phone,csrf):
    code=post(tv,'/tv/api/pair/start').json['code']
    assert post(phone,'/tv/api/phone/confirm',{'code':code},csrf).status_code==200
    assert post(tv,'/tv/api/pair/poll').json['state']=='linked'
    return get(tv,'/tv/api/me').json['csrf']

def test_existing_paid_account_and_shared_list_without_download_mutations(integrated):
    router,system=integrated;phone,tv=client(router),client(router)
    login=register(phone).json;uid=login['user']['id'];grant(system,uid,time.time()+3600)
    before=copy.deepcopy(system.supabase_service.rows)
    csrf=pair(tv,phone,login['csrf_token'])
    assert get(tv,'/tv/api/me').json['active'] and not get(tv,'/tv/api/me').json['permanent']
    assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==200
    assert post(tv,'/tv/api/list',{'id':1,'saved':True},csrf).status_code==200
    from services.profiles import Profiles
    assert Profiles(system.security_store).snapshot(uid)['saved_ids']==[1]
    assert system.supabase_service.rows==before
    with system.security_store.engine.connect() as c:assert c.execute(select(devices.c.account_id)).scalar_one()==uid
    assert get(phone,'/api/auth/me').json['user']['id']==uid

def test_verified_owner_keeps_permanent_access_but_tv_is_never_admin(integrated):
    router,system=integrated;phone,tv=client(router),client(router)
    login=tg_login(phone,5824989040).json;csrf=pair(tv,phone,login['csrf_token'])
    grant(system,login['user']['id'],0)
    assert get(tv,'/tv/api/me').json['permanent'] is True
    assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==200
    assert post(tv,'/api/admin/usuarios',{},csrf).status_code==401
    token=tv.get_cookie(LIVE_TV_COOKIE,domain='127.0.0.1',path='/tv').value
    tv.set_cookie(COOKIE,token,domain='127.0.0.1')
    assert get(tv,'/api/auth/me').json['authenticated'] is False
    assert post(tv,'/tv/api/phone/confirm',{'code':'ABCD-2345'},csrf).status_code==401
    # The bounded TV authentication does not become an unlimited session.
    with system.security_store.engine.begin() as c:c.execute(devices.update().values(expires_at=0))
    assert get(tv,'/tv/api/me').json['linked'] is False

@pytest.mark.parametrize('telegram_id',[7798025336,7233740331,5913015573])
def test_other_telegram_ids_do_not_inherit_owner_access(integrated,telegram_id):
    router,_=integrated;phone,tv=client(router),client(router)
    login=tg_login(phone,telegram_id).json;csrf=pair(tv,phone,login['csrf_token'])
    me=get(tv,'/tv/api/me').json
    assert me['linked'] and not me['permanent'] and not me['active']
    assert post(tv,'/tv/api/play',{'id':1,'telegram_id':5824989040},csrf).status_code==403

def test_membership_expiry_and_renewal_without_pairing_again(integrated):
    router,system=integrated;phone,tv=client(router),client(router)
    login=register(phone).json;uid=login['user']['id'];csrf=pair(tv,phone,login['csrf_token'])
    assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==403
    grant(system,uid,time.time()+3600);assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==200
    grant(system,uid,0);assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==403
    grant(system,uid,time.time()+3600);assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==200

def test_legacy_telegram_membership_uses_existing_checker(integrated):
    router,system=integrated;phone,tv=client(router),client(router)
    login=tg_login(phone,900000001).json
    assert system.account_legacy_expiry(login['user']['id'])>time.time()
    csrf=pair(tv,phone,login['csrf_token'])
    assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==200
    system.supabase_service.rows['usuarios'][0]['membresia_activa']=False
    assert post(tv,'/tv/api/play',{'id':1},csrf).status_code==403

def test_password_change_invalidates_device_and_approved_pending_code(integrated):
    router,_=integrated;phone,tv,pending=client(router),client(router),client(router)
    login=register(phone).json;pair(tv,phone,login['csrf_token'])
    code=post(pending,'/tv/api/pair/start').json['code']
    assert post(phone,'/tv/api/phone/confirm',{'code':code},login['csrf_token']).status_code==200
    changed=post(phone,'/api/auth/password',{'current_password':'Local-user-test-2026!','password':'Changed-local-password-2026!'},login['csrf_token'])
    assert changed.status_code==200
    assert get(tv,'/tv/api/me').json['linked'] is False
    assert post(pending,'/tv/api/pair/poll').json['state']=='expired'
    assert get(phone,'/api/auth/me').json['authenticated'] is True

def test_revoke_preserves_phone_login_and_code_cannot_be_claimed_twice(integrated):
    router,_=integrated;phone,tv=client(router),client(router)
    login=register(phone).json;pair(tv,phone,login['csrf_token'])
    assert post(phone,'/tv/api/phone/revoke').status_code==403
    assert post(phone,'/tv/api/phone/revoke',{},login['csrf_token']).status_code==200
    assert not get(tv,'/tv/api/me').json['linked']
    assert get(phone,'/api/auth/me').json['authenticated']
    assert post(tv,'/tv/api/pair/poll').json['state']=='expired'

def test_restart_preserves_device_and_web_routes_remain_identical(integrated):
    router,system=integrated;phone,tv=client(router),client(router)
    login=register(phone).json;pair(tv,phone,login['csrf_token'])
    token=tv.get_cookie(LIVE_TV_COOKIE,domain='127.0.0.1',path='/tv').value
    fresh=compose(system.app,system.supabase_service,system.security_store,system.account_legacy_expiry,enabled=True)
    other=client(fresh);other.set_cookie(LIVE_TV_COOKIE,token,domain='127.0.0.1',path='/tv')
    assert get(other,'/tv/api/me').json['linked']
    plain=system.app.test_client()
    for path in ('/','/cuenta','/membresia','/static/account.js','/health'):
        a=get(plain,path);b=get(other,path);assert a.status_code==b.status_code and a.data==b.data
    assert compose(system.app,None,None,None,enabled=False) is system.app
    assert get(other,'/tvanything').status_code==get(plain,'/tvanything').status_code

def test_public_assets_do_not_query_accounts_or_accept_forged_origins(integrated):
    router,system=integrated;c=client(router);statements=[]
    def track(*args):statements.append(args[2])
    event.listen(system.security_store.engine,'before_cursor_execute',track)
    try:
        for path in ('/tv','/tv/vincular','/tv/assets/tv.js','/tv/brand'):assert get(c,path).status_code==200
        assert statements==[]
    finally:event.remove(system.security_store.engine,'before_cursor_execute',track)
    assert c.post('/tv/api/pair/start',base_url=ORIGIN,json={},headers={'Origin':'https://evil.test'}).status_code==403
    assert post(c,'/tv/api/phone/login',{'email':'tv@example.test','password':'Televisor-Local-2026!'}).status_code==404
    html=get(c,'/tv/vincular').get_data(as_text=True)
    assert 'Televisor-Local-2026!' not in html and 'link-account.js' in html

def test_https_integration_cookie_contract_without_remote_database(integrated):
    _,system=integrated;s=system.security_store
    # Exercise HTTPS policy with local storage, not a Supabase connection.
    adapter=SimpleNamespace(local=False,engine=s.engine,allow_attempt=s.allow_attempt,session=s.session,account=s.account)
    app=create_app(system.supabase_service,adapter,'https://app.quehay.live',integrated=True)
    c=app.test_client();r=c.post('/tv/api/pair/start',base_url='https://app.quehay.live',json={},headers={'Origin':'https://app.quehay.live'})
    assert r.status_code==200
    assert all(x in r.headers['Set-Cookie'] for x in ('Secure','HttpOnly','SameSite=Strict','Path=/tv'))
    assert r.headers['Strict-Transport-Security']=='max-age=31536000'
    with pytest.raises(RuntimeError):create_app(system.supabase_service,adapter,'http://app.quehay.live',integrated=True)


def test_install_keeps_main_flask_app_and_existing_routes(system):
    app=system.app;original=app.wsgi_app
    before={p:get(app.test_client(),p).data for p in ('/','/cuenta','/health','/membresia')}
    try:
        install(app,system.supabase_service,system.security_store,system.account_legacy_expiry)
        router=app.wsgi_app
        install(app,system.supabase_service,system.security_store,system.account_legacy_expiry)
        assert app.wsgi_app is router
        c=app.test_client()
        for p,body in before.items():assert get(c,p).data==body
        assert get(c,'/tv').status_code==200
        phone,tv=app.test_client(),app.test_client()
        login=tg_login(phone,5824989040).json
        pair(tv,phone,login['csrf_token'])
        assert get(tv,'/tv/api/me').json['permanent'] is True
    finally:
        app.wsgi_app=original;app.extensions.pop('tv_router',None)
