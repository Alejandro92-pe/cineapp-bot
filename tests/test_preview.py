import pytest
from flask import Flask
from services.preview import validate_preview_origin

ORIGIN='https://test-preview.ngrok-free.dev'

@pytest.mark.parametrize('origin',['http://test.ngrok-free.dev','https://test.ngrok-free.dev.evil.test','https://test.ngrok-free.dev/path','https://user@test.ngrok-free.dev','https://test.ngrok-free.dev:443','https://test.ngrok-free.dev?x=1','https://test.ngrok-free.dev#frag'])
def test_tunnel_rejects_unsafe_origins(origin):
    with pytest.raises(ValueError): validate_preview_origin(origin)

@pytest.fixture
def preview(monkeypatch,tmp_path):
    monkeypatch.setenv('APP_MODE','local');monkeypatch.setenv('TELEGRAM_PREVIEW','true')
    monkeypatch.setenv('APP_ORIGIN',ORIGIN)
    monkeypatch.setenv('SECURITY_DATABASE_URL','sqlite:///'+(tmp_path/'preview.sqlite').as_posix())
    monkeypatch.setenv('BOT_TOKEN','123456:PREVIEW_TEST_ONLY')
    from security import install_security
    from pathlib import Path
    app=Flask(__name__,root_path=str(Path(__file__).resolve().parents[1]));install_security(app,lambda _:False)
    return app.test_client()

def test_preview_secure_cookie_exact_host_and_origin(preview):
    payload={'name':'Test','email':'preview@example.test','password':'Long-test-only-password!'}
    assert preview.post('/api/auth/register',json=payload,base_url='http://localhost:5011').status_code==403
    assert preview.post('/api/auth/register',json=payload,base_url=ORIGIN,headers={'Origin':'https://evil.test'}).status_code==403
    response=preview.post('/api/auth/register',json=payload,base_url=ORIGIN,headers={'Origin':ORIGIN})
    assert response.status_code==200
    cookie=response.headers['Set-Cookie']
    assert 'Secure;' in cookie and 'HttpOnly;' in cookie and 'SameSite=Lax' in cookie
    assert preview.get('/api/auth/me',base_url=ORIGIN).json['local'] is True

@pytest.mark.parametrize('path',['/cron/vencimientos','/webhook/bmc','/123456:PREVIEW_TEST_ONLY','/api/admin/vimeus/importar'])
def test_preview_blocks_production_integrations(preview,path):
    assert preview.post(path,base_url=ORIGIN).status_code in (403,503)

def test_preview_keeps_real_telegram_sdk(preview):
    response=preview.get('/cuenta',base_url=ORIGIN)
    assert response.status_code==200
    assert b'https://telegram.org/js/telegram-web-app.js' in response.data
    assert b'/static/telegram-local.js' not in response.data

def test_preview_does_not_trust_unsigned_telegram(preview):
    response=preview.post('/api/auth/telegram',base_url=ORIGIN,headers={'Origin':ORIGIN},json={'init_data':'user=5824989040'})
    assert response.status_code==401
