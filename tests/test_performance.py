"""Database work stays off public assets, without caching authorization."""
from sqlalchemy import event
from conftest import owner_login, send


def test_authenticated_public_load_does_not_query_sessions(client, system, monkeypatch):
    owner_login(client)
    calls=[]
    original=system.security_store.session
    def tracked(token):
        calls.append(True)
        return original(token)
    monkeypatch.setattr(system.security_store, 'session', tracked)
    for path in ['/', '/cuenta', '/admin', '/membresia', '/instalar', '/health',
                 '/static/app.js', '/static/styles.css', '/static/catalog/detail-loader.js',
                 '/api/tendencias', '/api/top10']:
        response=send(client,path,method='GET')
        assert response.status_code==200, path
        assert response.headers['X-Content-Type-Options']=='nosniff'
    assert send(client,'/api/contenido',{'limit':12}).status_code==200
    assert calls==[]
    assert send(client,'/api/payments/mine',method='GET').json['permanent']
    assert len(calls)==1
    assert send(client,'/api/playback/1',method='GET').status_code==200
    assert len(calls)==2


def test_session_identity_uses_one_select_and_revocation_is_immediate(client, system):
    owner_login(client)
    statements=[]
    def record(conn,cursor,statement,params,context,many):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    event.listen(system.security_store.engine,'before_cursor_execute',record)
    try:
        info=send(client,'/api/auth/me',method='GET').json
        assert info['user']['telegram_id']==5824989040 and info['is_admin']
        assert len(statements)==1
    finally:event.remove(system.security_store.engine,'before_cursor_execute',record)
    send(client,'/api/auth/logout',{},info['csrf_token'])
    assert send(client,'/api/playback/1',method='GET').status_code==401


def test_catalogue_still_rejects_cross_origin_and_strips_private_links(client):
    assert send(client,'/api/contenido',{'limit':12},headers={'Origin':'https://other.test'}).status_code==403
    rows=send(client,'/api/contenido',{'limit':12}).json['data']
    assert all('descarga' not in row and 'enlace_canal' not in row for row in rows)
