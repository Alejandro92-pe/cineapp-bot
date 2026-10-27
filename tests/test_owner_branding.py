import time
from urllib.parse import urlsplit, parse_qs
import pytest
from conftest import owner_login, register, send, tg_login, signed_telegram
from billing.schema import access, orders
from security_store import sessions
from services.local_vimeus import DemoVimeus
from services.vimeus_import import ImportRepository, import_title
from providers.player_brand import quehay_player_params


def test_brand_logo_uses_configured_https_origin_not_browser_input():
    assert quehay_player_params('https://quehay.example')['logo_url'] == 'https://quehay.example/static/logo-que-hay-live.png'
    for value in ['', 'http://127.0.0.1:5010', 'https://user:secret@example.test', 'https://example.test/?unsafe=1']:
        assert 'logo_url' not in quehay_player_params(value)


def test_owner_has_permanent_access_without_membership_or_payment_rows(client, system):
    owner_login(client)
    info = send(client, '/api/payments/mine', method='GET').json
    assert info['active'] and info['permanent'] and info['access_source'] == 'owner'
    assert info['expires_at'] is None
    assert send(client, '/api/playback/1', method='GET').status_code == 200
    assert send(client, '/api/download/1', method='GET').status_code == 200
    with system.security_store.engine.connect() as c:
        assert list(c.execute(access.select())) == []
        assert list(c.execute(orders.select())) == []


def test_telegram_verified_owner_has_the_same_access(client):
    assert tg_login(client, 5824989040).status_code == 200
    assert send(client, '/api/payments/mine', method='GET').json['permanent'] is True
    assert send(client, '/api/download/1', method='GET').status_code == 200


def test_owner_exemption_never_replaces_session_verification(client, system):
    auth = owner_login(client)
    with system.security_store.engine.begin() as c:
        c.execute(sessions.update().values(expires_at=time.time()-1))
    assert send(client, '/api/playback/1', method='GET').status_code == 401
    assert send(client, '/api/download/1', method='GET').status_code == 401
    assert send(client, '/api/payments/mine', method='GET').status_code == 401
    fake = signed_telegram(900000002).replace('900000002', '5824989040')
    assert send(client, '/api/auth/telegram', {'init_data': fake}).status_code != 200


def test_other_users_cannot_claim_owner_access_and_still_need_membership(client, system):
    auth = register(client)
    info = send(client, '/api/payments/mine', method='GET').json
    assert info['active'] is False and info['permanent'] is False
    assert send(client, '/api/playback/1', {'admin_id': 5824989040, 'telegram_id': 5824989040}, auth.json['csrf_token']).status_code == 403
    assert send(client, '/api/download/1?telegram_id=5824989040', method='GET').status_code == 403
    assert send(client, '/api/payments/orders', {'method': 'bmc'}, auth.json['csrf_token']).status_code == 200


@pytest.mark.parametrize('method', ['bmc', 'yape_plin', 'binance'])
def test_owner_is_not_offered_a_checkout(client, method):
    auth = owner_login(client)
    result = send(client, '/api/payments/orders', {'method': method}, auth.json['csrf_token'])
    assert result.status_code == 409 and result.json['code'] == 'owner_access'


@pytest.mark.parametrize('kind,tmdb', [('serie',900101), ('anime',900202)])
def test_branding_applies_to_exact_episodes_and_provider_selector(client, system, kind, tmdb):
    owner_login(client)
    result = import_title(DemoVimeus(), ImportRepository(system.supabase_service), tmdb, kind)
    episode = system.supabase_service.rows['episodios'][-1]
    for suffix in ['', f'?episodio_id={episode["id"]}']:
        response = send(client, f'/api/playback/{result["contenido_id"]}'+suffix, method='GET')
        assert response.status_code == 200
        parsed = urlsplit(response.json['url']);query = parse_qs(parsed.query)
        assert parsed.netloc == 'vimeus.com' and parsed.path == '/e/'+kind
        assert query['title'] == ['QueHay'] and query['theme'] == ['blue']
        assert query['primary_color'] == ['78b7fb'] and query['tmdb'] == [str(tmdb)]
        assert query['view_key'] == ['test-view-not-real']
        if suffix:
            assert query['ep'] == [str(episode['numero'])]
    # The owner's permanent access covers episode downloads too.
    system.supabase_service.table('episodios').update({'descarga':'https://www.mediafire.com/file/manual/file'}).eq('id', episode['id']).execute()
    assert send(client, f'/api/episode-download/{result["contenido_id"]}/{episode["id"]}', method='GET').status_code == 200


def test_movie_branding_ignores_client_supplied_overrides(client):
    auth = owner_login(client)
    result = send(client, '/api/playback/1', {'title':'Untrusted', 'primary_color':'ff0000'}, auth.json['csrf_token'])
    query = parse_qs(urlsplit(result.json['url']).query)
    assert query['title'] == ['QueHay'] and query['theme'] == ['blue']
