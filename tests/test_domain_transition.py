import pytest
from flask import Flask, jsonify

import security
from conftest import signed_telegram

NEW = 'https://app.quehay.live'
OLD = 'https://cineapp-bot.onrender.com'


@pytest.fixture
def migrated(system, monkeypatch):
    # Real authentication/session logic against the test SQLite store only.
    monkeypatch.setenv('APP_MODE', 'production')
    monkeypatch.setenv('APP_ORIGIN', NEW)
    monkeypatch.setenv('APP_ORIGIN_ALIASES', OLD)
    monkeypatch.setattr(security, 'SecurityStore', lambda *a, **k: system.security_store)
    app = Flask(__name__)
    app.config['TESTING'] = True
    security.install_security(app, lambda tid: tid == security.OWNER_ID)

    @app.post('/webhook/telegram')
    def telegram_hook():
        return jsonify(ok=True)

    @app.get('/cron/check')
    def cron():
        return jsonify(ok=True)

    from services.canonical_origin import CanonicalDocuments
    app.wsgi_app = CanonicalDocuments(app.wsgi_app, origin=NEW, local=False, mode='temporary')
    return app.test_client()


@pytest.mark.parametrize('origin', [NEW, OLD])
def test_both_exact_domains_accept_same_host_auth_and_secure_cookie(migrated, origin):
    response = migrated.post('/api/auth/telegram', json={'init_data': signed_telegram(security.OWNER_ID)},
                             base_url=origin, headers={'Origin': origin})
    assert response.status_code == 200
    assert response.json['user']['telegram_id'] == security.OWNER_ID
    assert 'Secure;' in response.headers['Set-Cookie']
    assert 'HttpOnly;' in response.headers['Set-Cookie']
    assert 'Domain=' not in response.headers['Set-Cookie']
    assert migrated.get('/api/auth/me', base_url=origin).json['authenticated'] is True
    # Adding an allowed alias never permits cross-origin authenticated writes.
    other = OLD if origin == NEW else NEW
    denied = migrated.post('/api/auth/logout', json={}, base_url=origin,
                           headers={'Origin': other, 'X-CSRF-Token': response.json['csrf_token']})
    assert denied.status_code == 403
    assert migrated.get('/api/auth/me', base_url=origin).json['authenticated'] is True
    assert migrated.post('/api/auth/logout', json={}, base_url=origin,
                         headers={'Origin': origin}).status_code == 403
    assert migrated.post('/api/auth/logout', json={}, base_url=origin,
                         headers={'Origin': origin, 'X-CSRF-Token': response.json['csrf_token']}).status_code == 200


def test_lookalike_host_and_forwarded_host_cannot_bypass_boundary(migrated):
    for host in ['https://app.quehay.live.evil.test', 'https://evil.test', 'https://quehay.live']:
        assert migrated.get('/health', base_url=host,
                            headers={'X-Forwarded-Host': 'app.quehay.live'}).status_code == 403


@pytest.mark.parametrize('origin', [NEW, OLD])
def test_webhook_and_cron_still_require_existing_secrets(migrated, origin):
    assert migrated.post('/webhook/telegram', json={}, base_url=origin).status_code == 401
    assert migrated.post('/webhook/telegram', json={}, base_url=origin,
                         headers={'X-Telegram-Bot-Api-Secret-Token': 'test-tg-secret-'*3}).status_code == 200
    assert migrated.get('/cron/check', base_url=origin).status_code == 401
    assert migrated.get('/cron/check', base_url=origin,
                        headers={'Authorization': 'Bearer '+'test-cron-secret-'*3}).status_code == 200


@pytest.mark.parametrize('alias', ['https://*.quehay.live', 'http://cineapp-bot.onrender.com',
    'https://user:password@example.com', 'https://example.com/path',
    'https://example.com?query=1', 'https://example.com#fragment'])
def test_invalid_aliases_fail_closed(alias):
    with pytest.raises(RuntimeError):
        security.trusted_origins(NEW, alias)


def test_local_preview_cannot_enable_public_aliases():
    with pytest.raises(RuntimeError):
        security.trusted_origins('http://127.0.0.1:5010', OLD, local=True)
