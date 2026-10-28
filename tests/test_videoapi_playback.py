import copy
import pytest
import requests
from urllib.parse import urlsplit, parse_qs
from conftest import send, owner_login, register
from providers.videoapi import Availability, embed_url


@pytest.fixture
def videoapi(system, monkeypatch):
    monkeypatch.setitem(system.app.config, 'VIDEOAPI_ENABLED', True)
    monkeypatch.setattr('services.videoapi_playback.available', lambda *args: True)
    return system


def test_membership_csrf_and_owner_still_required(client, videoapi):
    path = '/api/playback/1?provider=videoapi'
    assert send(client, path, method='GET').status_code == 401
    register(client)
    assert send(client, path, method='GET').status_code == 403
    session = owner_login(client)
    assert send(client, path, {}).status_code == 403
    result = send(client, path, {}, session.json['csrf_token'])
    assert result.status_code == 200
    assert urlsplit(result.json['url']).path == '/e/movie/1'
    assert parse_qs(urlsplit(result.json['url']).query) == {
        'primary_color': ['78b7fb'], 'secondary_color': ['111d30'], 'icon_color': ['edf5ff']}


def test_default_and_manual_fallback_preserve_catalog_and_downloads(client, videoapi, monkeypatch):
    owner_login(client)
    before = copy.deepcopy(videoapi.supabase_service.rows)
    assert send(client, '/api/playback/1', method='GET').json['provider'] == 'videoapi'
    assert send(client, '/api/playback/1?provider=vimeus', method='GET').json['provider'] == 'vimeus'
    monkeypatch.setattr('services.videoapi_playback.available', lambda *args: False)
    assert send(client, '/api/playback/1?provider=videoapi', method='GET').json['provider'] == 'vimeus'
    assert videoapi.supabase_service.rows == before
    assert send(client, '/api/download/1', method='GET').json['url'] == before['contenido'][0]['descarga']


def test_production_ignores_local_allowlist_and_supports_kill_switch(client, videoapi, monkeypatch):
    owner_login(client)
    monkeypatch.setitem(videoapi.app.config, 'SECURITY_LOCAL', False)
    monkeypatch.setitem(videoapi.app.config, 'VIDEOAPI_PILOT', {})
    assert send(client, '/api/playback/1', method='GET').json['provider'] == 'videoapi'
    assert send(client, '/api/contenido', {'id': 1}).json['data'][0]['videoapi_enabled'] is True
    assert 'frame-src https://videoapi.la ' in client.get('/').headers['Content-Security-Policy']
    monkeypatch.setitem(videoapi.app.config, 'VIDEOAPI_ENABLED', False)
    assert send(client, '/api/playback/1', method='GET').json['provider'] == 'vimeus'
    assert send(client, '/api/playback/1?provider=videoapi', method='GET').status_code == 404


def test_episode_ownership_and_any_imported_episode(client, videoapi):
    db = videoapi.supabase_service
    db.rows['contenido'][0].update(tipo='anime')
    db.rows['temporadas'] = [{'id': 10, 'contenido_id': 1, 'numero': 2}, {'id': 11, 'contenido_id': 2, 'numero': 1}]
    db.rows['episodios'] = [{'id': 20, 'temporada_id': 10, 'numero': 10, 'disponible': True}, {'id': 21, 'temporada_id': 11, 'numero': 1, 'disponible': True}, {'id': 22, 'temporada_id': 10, 'numero': 2, 'disponible': False}]
    owner_login(client)
    result = send(client, '/api/playback/1?episodio_id=20', method='GET')
    assert urlsplit(result.json['url']).path == '/e/anime/1/2/10'
    for ep in [21, 22, 999]:
        assert send(client, f'/api/playback/1?episodio_id={ep}', method='GET').status_code == 404
    assert send(client, '/api/playback/1?episodio_id=wrong', method='GET').status_code == 400
    assert send(client, '/api/playback/1', method='GET').json['provider_selection'] is True


def test_okru_and_legacy_sources_not_overridden(client, videoapi):
    owner_login(client)
    videoapi.supabase_service.rows['contenido'][0].update(fuente='okru', playback_url='https://ok.ru/video/123')
    assert send(client, '/api/playback/1', method='GET').json['provider'] == 'okru'
    assert send(client, '/api/playback/1?provider=videoapi', method='GET').status_code == 404
    assert send(client, '/api/playback/1?provider=https://evil.test', method='GET').status_code == 400


def test_availability_caches_checks_and_limits_timeouts():
    calls, now = [], [0]
    class Response:
        status_code = 200
        def json(self): return {'exists': True, 'path': '/e/movie/1'}
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    check = Availability(get=get, clock=lambda: now[0])
    assert check('pelicula', 1) and check('pelicula', 1)
    assert len(calls) == 1
    assert calls[0] == ('https://videoapi.la/api/v1/public/exists/movie/1', {'timeout': (1.5, 2), 'allow_redirects': False})
    now[0] = 1801
    assert check('pelicula', 1) and len(calls) == 2


@pytest.mark.parametrize('failure', ['timeout', '503', 'malformed', 'foreign_path'])
def test_unavailable_provider_falls_back_without_trusting_response(failure):
    class Response:
        status_code = 503 if failure == '503' else 200
        def json(self):
            if failure == 'malformed': raise ValueError()
            return {'exists': True, 'path': 'https://evil.test/video'}
    def get(*args, **kwargs):
        if failure == 'timeout': raise requests.Timeout()
        return Response()
    assert Availability(get=get)('pelicula', 1) is False


@pytest.mark.parametrize('kind,tmdb,season,episode', [('movie',1,None,None), ('pelicula','1/evil',None,None), ('serie',1,None,None), ('anime',1,1,0)])
def test_embed_rejects_invalid_identifiers(kind, tmdb, season, episode):
    with pytest.raises(ValueError): embed_url(kind, tmdb, season, episode)
