"""vimeus.com can show a parked 'domain expired' page with HTTP 200: never embed it."""
import requests
import pytest
from providers.vimeus_health import VimeusHealth
from conftest import send, tg_login


class Response:
    def __init__(self, status=200, text='', headers=None):
        self.status_code, self.text, self.headers = status, text, headers or {}


def health(*responses):
    calls = []
    clock = {'now': 0.0}
    def get(url, **kwargs):
        calls.append(url)
        r = responses[min(len(calls), len(responses)) - 1]
        if isinstance(r, Exception):
            raise r
        return r
    return VimeusHealth(get=get, clock=lambda: clock['now']), calls, clock


@pytest.mark.parametrize('response', [
    Response(200, '<script>window.onload=function(){window.location.href="/lander"}</script>'),
    Response(200, 'This domain has expired. If you owned this name, contact your registration provider'),
    Response(302, '', {'Location': 'https://vimeus.com/lander'}),
    Response(503, 'down'),
    requests.ConnectionError('dns'),
])
def test_parked_or_unreachable_vimeus_is_down(monkeypatch, response):
    monkeypatch.delenv('VIMEUS_DISABLED', raising=False)
    check, _, _ = health(response)
    assert check() is False


def test_healthy_vimeus_is_cached_and_rechecked(monkeypatch):
    monkeypatch.delenv('VIMEUS_DISABLED', raising=False)
    check, calls, clock = health(Response(200, '<html>Vimeus player</html>'), Response(200, 'window.location.href="/lander"'))
    assert check() is True and check() is True and len(calls) == 1
    clock['now'] = 601
    assert check() is False and len(calls) == 2
    clock['now'] = 650
    assert check() is False and len(calls) == 2  # a broken provider is re-checked after two minutes


def test_manual_switch_disables_vimeus(monkeypatch):
    monkeypatch.setenv('VIMEUS_DISABLED', 'true')
    check, calls, _ = health(Response(200, 'ok'))
    assert check() is False and calls == []


def test_playback_refuses_dead_vimeus_instead_of_embedding_it(client, system, monkeypatch):
    from test_vimeus import import_api
    cid = import_api(client)['contenido_id']
    user = system.app.test_client(); tg_login(user)
    monkeypatch.setitem(system.app.config, 'VIMEUS_HEALTH', True)
    monkeypatch.setattr('providers.vimeus_health.vimeus_up', lambda: False)
    result = send(user, f'/api/playback/{cid}', method='GET')
    assert result.status_code == 503, result.json
    assert result.json.get('code') == 'provider_down' and 'url' not in result.json, result.json
    monkeypatch.setattr('providers.vimeus_health.vimeus_up', lambda: True)
    assert 'vimeus.com/e/anime' in send(user, f'/api/playback/{cid}', method='GET').json['url']


def test_security_layer_keeps_coded_errors_but_hides_anything_else(system):
    from flask import jsonify
    from security import deliberate_error
    with system.app.test_request_context():
        assert deliberate_error(jsonify(error='Reproductor caído.', code='provider_down', provider='vimeus'))
        assert not deliberate_error(jsonify(error='Algo falló.'))                      # no code: generic message
        assert not deliberate_error(jsonify(error='x', code='y', trace='stack'))       # extra fields never pass
        assert not deliberate_error(jsonify(error='x' * 301, code='y'))
        assert not deliberate_error(jsonify(error='x', code='y', provider='https://evil'))
