import time
from conftest import owner_login, register, send, tg_login


def test_owner_keeps_viewing_after_admin_hour_but_admin_actions_expire(client, system, monkeypatch):
    initial = time.time()
    response = owner_login(client)
    csrf = response.json['csrf_token']
    assert 'Max-Age=604800' in response.headers['Set-Cookie']
    monkeypatch.setattr('security_store.time.time', lambda: initial+7200)
    me = send(client, '/api/auth/me', method='GET')
    assert me.json['authenticated'] and not me.json['is_admin']
    assert send(client, '/api/playback/1', {}, csrf).status_code == 200
    assert send(client, '/api/download/1', method='GET').status_code == 200
    assert send(client, '/api/admin/catalog/queue', method='GET').status_code == 403
    monkeypatch.setattr('security_store.time.time', lambda: initial+604801)
    assert send(client, '/api/playback/1', {}, csrf).status_code == 401


def test_regular_account_stays_signed_in_without_granting_membership(client, monkeypatch):
    initial = time.time()
    response = register(client); csrf=response.json['csrf_token']
    monkeypatch.setattr('security_store.time.time', lambda: initial+50000)
    assert send(client, '/api/auth/me', method='GET').json['authenticated']
    assert send(client, '/api/playback/1', {}, csrf).status_code == 403
    assert send(client, '/api/auth/logout', {}, csrf).status_code == 200
    assert not send(client, '/api/auth/me', method='GET').json['authenticated']


def test_stale_tab_csrf_has_explicit_pre_handler_rejection(client):
    old = owner_login(client).json['csrf_token']
    current = owner_login(client).json['csrf_token']
    response = send(client, '/api/playback/1', {}, old)
    assert response.status_code == 403 and response.json['code'] == 'csrf_refresh_required'
    assert send(client, '/api/auth/me', method='GET').json['csrf_token'] == current
    assert send(client, '/api/playback/1', {}, current).status_code == 200


def test_telegram_owner_viewing_survives_old_init_data_without_reusing_signature(client, monkeypatch):
    initial=time.time(); response=tg_login(client,5824989040)
    monkeypatch.setattr('security_store.time.time',lambda:initial+14400)
    assert send(client,'/api/playback/1',{},response.json['csrf_token']).status_code==200


def test_missing_admin_lease_never_grants_seven_days_of_admin(client, system):
    from security_store import admin_leases
    owner_login(client)
    with system.security_store.engine.begin() as c:c.execute(admin_leases.delete())
    me=send(client,'/api/auth/me',method='GET').json
    assert me['authenticated'] and not me['is_admin']
    assert send(client,'/api/playback/1',method='GET').status_code==200
