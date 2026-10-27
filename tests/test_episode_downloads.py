import pytest
from conftest import send, owner_login, tg_login, register
from services.vimeus_import import import_title, ImportRepository
from services.local_vimeus import DemoVimeus


def setup_episode(system):
    db=system.supabase_service
    result=import_title(DemoVimeus(),ImportRepository(db),900202,'anime')
    ep=db.rows['episodios'][0]
    db.table('episodios').update({'descarga':'https://www.mediafire.com/file/episode-one/file'}).eq('id',ep['id']).execute()
    return result['contenido_id'],ep


def test_episode_url_private_and_entitlement_checked(client,system):
    cid,ep=setup_episode(system);url=f'/api/episode-download/{cid}/{ep["id"]}'
    metadata=send(client,f'/api/episodios/{cid}/{ep["temporada_id"]}',method='GET')
    assert metadata.json['episodios'][0]['has_download'] is True
    assert 'descarga' not in metadata.json['episodios'][0]
    assert send(client,url,method='GET').status_code==401
    register(client)
    assert send(client,url,method='GET').status_code==403
    member=system.app.test_client();tg_login(member)
    response=send(member,url,method='GET')
    assert response.status_code==200 and response.json['host']=='www.mediafire.com'
    assert 'no-store' in response.headers['Cache-Control']
    assert send(member,f'/api/episode-download/1/{ep["id"]}',method='GET').status_code==404
    system.supabase_service.table('episodios').update({'disponible':False}).eq('id',ep['id']).execute()
    assert send(member,url,method='GET').status_code==404


def test_only_owner_can_edit_and_reimport_preserves_episode_link(client,system):
    cid,ep=setup_episode(system);url=f'/api/admin/episode-download/{cid}/{ep["id"]}'
    user=register(client)
    assert send(client,url,{'url':'https://mediafire.com/file/test/file'},user.json['csrf_token']).status_code==403
    owner=owner_login(client)
    assert send(client,url,{'url':'https://mediafire.com/file/test/file'}).status_code==403
    assert send(client,url,{'url':'https://mediafire.com/file/test/file'},owner.json['csrf_token']).status_code==200
    import_title(DemoVimeus(),ImportRepository(system.supabase_service),900202,'anime')
    assert send(client,url,method='GET').json['url']=='https://mediafire.com/file/test/file'
    assert send(client,url,{'url':''},owner.json['csrf_token']).json['has_download'] is False


@pytest.mark.parametrize('link',['javascript:alert(1)','http://mediafire.com/file','https://u:p@mediafire.com/file','https://localhost/file',None])
def test_episode_download_rejects_unsafe_urls(client,system,link):
    cid,ep=setup_episode(system);owner=owner_login(client)
    assert send(client,f'/api/admin/episode-download/{cid}/{ep["id"]}',{'url':link},owner.json['csrf_token']).status_code==400


def test_unimported_series_has_authorized_provider_selector(client,system):
    db=system.supabase_service
    db.table('contenido').insert({'id':987,'tipo':'serie','tmdb_id':1399,'fuente':'vimeus','disponible':True}).execute()
    assert send(client,'/api/playback/987',method='GET').status_code==401
    tg_login(client)
    response=send(client,'/api/playback/987',method='GET')
    assert response.status_code==200 and response.json['provider_selection'] is True
    assert '/e/serie?' in response.json['url'] and '&ep=' not in response.json['url']
