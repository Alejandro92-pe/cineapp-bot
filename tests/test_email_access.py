import copy,time
import pytest
from sqlalchemy import select
from conftest import send,tg_login,signed_telegram,register
from security import COOKIE,password_ok
from security_store import accounts
from billing.schema import access
from services.profiles import Profiles

PASSWORD='Mi nueva clave privada 2026!'
def body(tid=5824989040,**extra):
    return {'email':'ale@example.test','password':PASSWORD,'password_confirmation':PASSWORD,
            'init_data':signed_telegram(tid),**extra}
def add(c,csrf,**extra):return send(c,'/api/auth/email-access',body(**extra),csrf)

@pytest.mark.parametrize('tid',[5824989040,900000201])
def test_same_account_paid_access_list_downloads_and_owner_after_email_login(client,system,tid):
    login=tg_login(client,tid).json;uid=login['user']['id']
    with system.security_store.engine.begin() as c:
        c.execute(access.insert().values(account_id=uid,expires_at=time.time()+86400))
    profiles=Profiles(system.security_store);profiles.mutate(uid,items=[(1,True)])
    saved=profiles.snapshot(uid);catalog=copy.deepcopy(system.supabase_service.rows)
    result=add(client,login['csrf_token'],tid=tid,email='  ALE@example.test  ')
    assert result.status_code==200 and result.json['user']['id']==uid
    assert result.json['user']['email_login_enabled'] and not result.json['is_admin']
    assert result.json['user']['telegram_id']==tid
    stored=system.security_store.account(id=uid)
    assert stored['email']=='ale@example.test' and stored['password_hash']!=PASSWORD and password_ok(PASSWORD,stored['password_hash'])
    # A separate APK/browser cookie jar logs in without Telegram initData.
    apk=system.app.test_client()
    auth=send(apk,'/api/auth/login',{'email':'ale@example.test','password':PASSWORD})
    assert auth.status_code==200 and auth.json['user']['id']==uid and not auth.json['is_admin']
    membership=send(apk,'/api/payments/mine',method='GET').json
    assert membership['active'] and membership['permanent']==(tid==5824989040)
    assert send(apk,'/api/download/1',method='GET').status_code==200
    assert send(apk,'/api/playback/1',method='GET').status_code==200
    assert send(apk,'/api/admin/usuarios',{},auth.json['csrf_token']).status_code==403
    assert profiles.snapshot(uid)==saved and system.supabase_service.rows==catalog
    with system.security_store.engine.connect() as c:assert len(c.execute(select(accounts)).all())==1
    assert tg_login(system.app.test_client(),tid).json['user']['id']==uid

def test_requires_session_csrf_and_fresh_matching_telegram(client,system):
    assert add(client,'').status_code==401
    login=tg_login(client).json;csrf=login['csrf_token'];tid=login['user']['telegram_id']
    assert add(client,'',tid=tid).status_code==403
    for proof,status in [('',401),(signed_telegram(tid,age=301),401),(signed_telegram(5824989040),403),
                         (signed_telegram(tid).replace(str(tid),'5824989040'),401)]:
        assert add(client,csrf,tid=tid,init_data=proof).status_code==status
    assert system.security_store.account(id=login['user']['id'])['email'] is None

@pytest.mark.parametrize('extra',[{'email':'not an email'},{'password':'short','password_confirmation':'short'},
                                {'password_confirmation':'different'}])
def test_invalid_inputs_do_not_change_identity(client,system,extra):
    login=tg_login(client,5824989040).json
    assert add(client,login['csrf_token'],**extra).status_code==400
    assert system.security_store.account(id=login['user']['id'])['password_hash'] is None

def test_duplicate_email_never_merges_or_revokes_on_failure(client,system):
    other=system.app.test_client();existing=register(other,'ale@example.test').json
    login=tg_login(client,5824989040).json;before=client.get_cookie(COOKIE,domain="127.0.0.1").value
    assert add(client,login['csrf_token']).status_code==409
    assert system.security_store.session(before)
    assert system.security_store.account(id=login['user']['id'])['email'] is None
    assert system.security_store.account(id=existing['user']['id'])['telegram_id'] is None

def test_replay_cannot_overwrite_and_previous_sessions_are_revoked(client,system):
    login=tg_login(client,5824989040).json;old=client.get_cookie(COOKIE,domain="127.0.0.1").value
    assert add(client,login['csrf_token']).status_code==200
    assert system.security_store.session(old) is None
    csrf=send(client,'/api/auth/me',method='GET').json['csrf_token']
    assert add(client,csrf,email='changed@example.test').status_code==409
    assert not system.security_store.add_email_credentials(login['user']['id'],5824989040,'changed@example.test','bad')
    assert system.security_store.account(id=login['user']['id'])['email']=='ale@example.test'

def test_existing_email_account_cannot_use_telegram_setup(client):
    login=register(client).json
    assert add(client,login['csrf_token']).status_code==409
