import copy
import pytest
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace
from conftest import send, owner_login, tg_login, register
from providers.vimeus import VimeusClient, ImportFailure
from services.local_vimeus import DemoVimeus
from services.vimeus_import import build_manifest, import_title, ImportRepository


class Transport:
    def __init__(self, transform=None, status=200):
        self.demo, self.calls, self.transform, self.status = DemoVimeus(), [], transform, status

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        filters = kwargs['params'].copy()
        page = filters.pop('page')
        resource = url.rsplit('/', 1)[-1]
        rows, pagination = self.demo.page(resource, page, **filters)
        payload = {'error': False, 'data': {resource: rows, 'pagination': pagination}}
        if self.transform:
            self.transform(payload, page)
        return SimpleNamespace(status_code=self.status, json=lambda: payload)


def test_all_pages_all_seasons_and_private_header():
    transport = Transport()
    rows = VimeusClient('private-list-key', transport).episodes(900202, 'anime')
    assert len(rows) == 72 and rows[-1]['season'] == 2 and rows[-1]['episode'] == 12
    assert [call[1]['params']['page'] for call in transport.calls] == [1, 2]
    assert all(call[1]['headers'] == {'X-API-Key': 'private-list-key'} and call[1]['allow_redirects'] is False for call in transport.calls)
    assert all('private-list-key' not in call[0] for call in transport.calls)


@pytest.mark.parametrize('mutate', [
    lambda p,n: p['data']['pagination'].update(current_page=1) if n == 2 else None,
    lambda p,n: p['data']['pagination'].update(total_results=73) if n == 2 else None,
    lambda p,n: p['data']['episodes'].pop(),
    lambda p,n: p['data']['episodes'][0].update(tmdb_id=99),
    lambda p,n: p['data']['episodes'][0].update(content_type='series'),
    lambda p,n: p['data']['episodes'][0].update(episode=0),
    lambda p,n: p['data']['episodes'][0].update(season=-1),
    lambda p,n: p['data']['episodes'][1].update(season=1, episode=1),
    lambda p,n: p['data']['episodes'][1].update(id=p['data']['episodes'][0]['id']),
    lambda p,n: p['data']['pagination'].update(has_next='yes'),
])
def test_malformed_or_partial_snapshot_never_writes(system, mutate):
    before = copy.deepcopy(system.supabase_service.rows)
    with pytest.raises(ImportFailure):
        import_title(VimeusClient('key', Transport(mutate)), ImportRepository(system.supabase_service), 900202, 'anime')
    assert system.supabase_service.rows == before


@pytest.mark.parametrize('status', [301,401,403,404,429,500,502,503,504])
def test_provider_errors_fail_closed(status):
    transport = Transport(status=status)
    with pytest.raises(ImportFailure):
        VimeusClient('key', transport).episodes(900202, 'anime')
    assert len(transport.calls) <= 2


def test_no_key_does_not_attempt_network():
    transport = Transport()
    with pytest.raises(ImportFailure, match='VIMEUS_API_KEY'):
        VimeusClient('', transport).episodes(900202, 'anime')
    assert transport.calls == []


def test_tmdb_enriches_only_available_provider_episodes():
    def tmdb(path):
        if '/season/' not in path:
            return {'name':'Editorial title','seasons':[{'season_number':1,'name':'Primera'}]}
        return {'episodes':[{'episode_number':1,'name':'El inicio','overview':'Sinopsis','runtime':24},
                            {'episode_number':999,'name':'Unavailable'}]}
    manifest, warnings = build_manifest(DemoVimeus(), 900202, 'anime', tmdb)
    assert warnings == [] and manifest['contenido']['titulo'] == 'Editorial title'
    episodes = [e for s in manifest['temporadas'] for e in s['capitulos']]
    assert len(episodes) == 72 and episodes[0]['titulo'] == 'El inicio'
    assert not any(e['numero'] == 999 for e in episodes)


def test_tmdb_outage_does_not_lose_available_episodes():
    def offline(path): raise TimeoutError('private URL must not leak')
    manifest, warnings = build_manifest(DemoVimeus(), 900202, 'anime', offline)
    assert len(warnings) == 3 and 'private URL' not in str(warnings)
    assert sum(len(s['capitulos']) for s in manifest['temporadas']) == 72


def test_reimport_preserves_ids_downloads_season_links_editorial_and_hidden_status(system):
    db = system.supabase_service
    repository = ImportRepository(db)
    first = import_title(DemoVimeus(), repository, 900101, 'serie')
    cid = first['contenido_id']
    original_ids = [e['id'] for e in db.rows['episodios']]
    download = 'https://www.mediafire.com/file/preserved/file'
    db.table('contenido').update({'descarga':download,'titulo':'Mi título','disponible':False}).eq('id',cid).execute()
    db.table('temporadas').update({'enlace':'https://example.org/preserved','nombre':'Mi temporada'}).eq('contenido_id',cid).execute()
    second = import_title(DemoVimeus(), repository, 900101, 'serie')
    assert second['creados'] == 0 and second['actualizados'] == 15
    assert original_ids == [e['id'] for e in db.rows['episodios']]
    content = db.table('contenido').select('*').eq('id',cid).execute().data[0]
    assert content['descarga'] == download and content['titulo'] == 'Mi título' and content['disponible'] is False
    assert all(t['nombre'] == 'Mi temporada' and t['enlace'] == 'https://example.org/preserved' for t in db.rows['temporadas'])
    assert any(t['numero'] == 0 for t in db.rows['temporadas'])


def test_complete_resync_retires_but_does_not_delete_missing_episodes(system):
    db, provider = system.supabase_service, DemoVimeus()
    import_title(provider, ImportRepository(db), 900202, 'anime')
    provider.items[900202] = ('anime', 'Shorter listing', [(1, 59)])
    result = import_title(provider, ImportRepository(db), 900202, 'anime')
    assert result['retirados'] == 13 and len(db.rows['episodios']) == 72
    assert sum(ep['disponible'] for ep in db.rows['episodios']) == 59


def test_database_failure_rolls_back(system, monkeypatch):
    from local_support import Query
    original = Query.execute
    def fail(self):
        if self.name == 'episodios' and self.operation == 'insert' and self.payload['numero'] == 3:
            raise RuntimeError('Simulated disk failure')
        return original(self)
    monkeypatch.setattr(Query, 'execute', fail)
    before = copy.deepcopy(system.supabase_service.rows)
    with pytest.raises(RuntimeError):
        import_title(DemoVimeus(), ImportRepository(system.supabase_service), 900202, 'anime')
    assert system.supabase_service.rows == before


def import_api(client, kind='anime', tmdb=900202):
    auth = owner_login(client)
    response = send(client, '/api/admin/vimeus/importar', {'tmdb_id':tmdb,'tipo':kind}, auth.json['csrf_token'])
    assert response.status_code == 200
    return response.json


def test_admin_only_and_csrf(client):
    assert send(client, '/api/admin/vimeus/catalogo', method='GET').status_code == 403
    assert send(client, '/api/admin/vimeus/importar', {'tmdb_id':900202,'tipo':'anime'}).status_code == 401
    auth = register(client)
    assert send(client, '/api/admin/vimeus/importar', {'tmdb_id':900202,'tipo':'anime'}, auth.json['csrf_token']).status_code == 403
    owner_login(client)
    assert send(client, '/api/admin/vimeus/importar', {'tmdb_id':900202,'tipo':'anime'}).status_code == 403


@pytest.mark.parametrize('value', [0,-1,True,'abc',None,2.5,2147483648])
def test_bad_tmdb_id_rejected(client, value):
    auth = owner_login(client)
    assert send(client, '/api/admin/vimeus/importar', {'tmdb_id':value,'tipo':'anime'}, auth.json['csrf_token']).status_code == 422


def test_import_api_and_public_pagination_without_leaking_links(client, system):
    result = import_api(client)
    assert result['temporadas'] == 2 and result['episodios'] == 72
    cid = result['contenido_id']
    seasons = send(client,f'/api/temporadas/{cid}',method='GET').json['temporadas']
    public = system.app.test_client()
    first = send(public,f'/api/episodios/{cid}/{seasons[0]["id"]}',method='GET')
    second = send(public,f'/api/episodios/{cid}/{seasons[0]["id"]}?page=2',method='GET')
    assert len(first.json['episodios']) == 50 and first.json['has_next']
    assert len(second.json['episodios']) == 10 and not second.json['has_next']
    assert second.json['episodios'][-1]['numero'] == 60
    assert 'vimeus_id' not in first.json['episodios'][0] and 'url=' not in first.text
    assert send(public,f'/api/episodios/1/{seasons[0]["id"]}',method='GET').status_code == 404


def test_playback_exact_episode_membership_and_cross_title(client, system):
    result = import_api(client)
    cid = result['contenido_id']
    ep = system.supabase_service.rows['episodios'][-1]
    user = system.app.test_client()
    url = f'/api/playback/{cid}?episodio_id={ep["id"]}'
    assert send(user,url,method='GET').status_code == 401
    tg_login(user)
    playback = send(user,url,method='GET')
    parsed = urlsplit(playback.json['url'])
    assert parsed.path == '/e/anime' and parse_qs(parsed.query)['se'] == ['2'] and parse_qs(parsed.query)['ep'] == ['12']
    selector = send(user,f'/api/playback/{cid}',method='GET')
    assert selector.status_code == 200 and selector.json['provider_selection'] is True
    assert 'ep' not in parse_qs(urlsplit(selector.json['url']).query)
    assert send(user,f'/api/playback/{cid}?episodio_id=invalid',method='GET').status_code == 400
    other = import_api(client,'serie',900101)
    assert send(user,f'/api/playback/{other["contenido_id"]}?episodio_id={ep["id"]}',method='GET').status_code == 404
    system.supabase_service.table('episodios').update({'disponible':False}).eq('id',ep['id']).execute()
    assert send(user,url,method='GET').status_code == 404
    system.supabase_service.rows['usuarios'][0]['fecha_vencimiento']='2020-01-01T00:00:00+00:00'
    assert send(user,url,method='GET').status_code == 403


def test_legacy_season_import_now_imports_chapters(client, system):
    result = import_api(client,'serie',900101)
    auth = owner_login(client)
    response = send(client,'/api/admin/importar_temporadas',{'contenido_id':result['contenido_id']},auth.json['csrf_token'])
    assert response.status_code == 200 and response.json['episodios'] == 15


def test_reimport_keeps_authenticated_mediafire_download(client, system):
    result = import_api(client)
    cid = result['contenido_id']
    link = 'https://www.mediafire.com/file/preserved/file'
    system.supabase_service.table('contenido').update({'descarga':link}).eq('id',cid).execute()
    import_api(client)
    user = system.app.test_client()
    tg_login(user)
    response = send(user,f'/api/download/{cid}',method='GET')
    assert response.status_code == 200 and response.json['url'] == link


def test_timeout_retries_are_bounded_and_private_errors_hidden():
    import requests
    class Timeout:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            raise requests.Timeout('secret private-key')
    transport = Timeout()
    with pytest.raises(ImportFailure) as exc:
        VimeusClient('secret',transport).episodes(900202,'anime')
    assert transport.calls == 2 and 'secret' not in str(exc.value)


def test_bad_episode_page_is_rejected(client, system):
    result = import_api(client)
    sid = system.supabase_service.rows['temporadas'][0]['id']
    for page in ('abc', '-1', '101', '1.5'):
        assert send(client,f'/api/episodios/{result["contenido_id"]}/{sid}?page={page}',method='GET').status_code == 400


def test_invalid_type_cannot_import(client):
    auth = owner_login(client)
    for kind in ('pelicula', None, [], {}):
        assert send(client,'/api/admin/vimeus/importar',{'tmdb_id':900202,'tipo':kind},auth.json['csrf_token']).status_code == 422
