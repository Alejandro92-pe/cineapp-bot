import pytest
from tv.app import create_app
from security_store import SecurityStore
from local_support import LocalDatabase

@pytest.mark.parametrize('origin', ['http://0.0.0.0:5021','http://8.8.8.8:5021','https://192.168.1.3:5021','http://192.168.1.3:5021/anything','http://user@192.168.1.3:5021','http://169.254.1.3:5021'])
def test_lan_does_not_open_public_or_ambiguous_origins(tmp_path, origin):
    security=SecurityStore('sqlite:///'+str(tmp_path/'demo.sqlite'),local=True)
    with pytest.raises(RuntimeError):create_app(LocalDatabase(),security,origin,lan_preview=True)

def test_lan_requires_explicit_flag_and_private_clients(tmp_path):
    security=SecurityStore('sqlite:///'+str(tmp_path/'demo.sqlite'),local=True)
    origin='http://192.168.100.3:5021'
    with pytest.raises(RuntimeError):create_app(LocalDatabase(),security,origin)
    app=create_app(LocalDatabase(),security,origin,lan_preview=True);c=app.test_client()
    assert c.get('/tv',base_url=origin,environ_overrides={'REMOTE_ADDR':'192.168.100.5'}).status_code==200
    assert c.get('/tv',base_url=origin,environ_overrides={'REMOTE_ADDR':'8.8.8.8'}).status_code==403
    assert c.get('/tv',base_url='http://evil.test:5021').status_code==403
    assert c.post('/tv/api/pair/start',base_url=origin,json={},headers={'Origin':'http://evil.test'}).status_code==403
    r=c.post('/tv/api/pair/start',base_url=origin,json={},headers={'Origin':origin})
    assert r.status_code==200 and r.json['url']==origin+'/tv/vincular'
    assert 'HttpOnly' in r.headers['Set-Cookie']
    for url in ['/membresia','/api/download/1','/api/admin/payments']:
        assert c.get(url,base_url=origin).status_code==404
