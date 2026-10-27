import pytest
from providers.okru import embed_url
from conftest import send, register, tg_login


@pytest.mark.parametrize('value',['https://ok.ru/video/10328454335072','https://ok.ru/videoembed/10328454335072?autoplay=1','https://www.ok.ru/video/10328454335072/'])
def test_canonical_embed(value):
    assert embed_url(value)=='https://ok.ru/videoembed/10328454335072?nochat=1'


@pytest.mark.parametrize('value',[None,'http://ok.ru/video/1','https://ok.ru.evil.test/video/1','https://ok.ru@evil.test/video/1','https://user@ok.ru/video/1','https://ok.ru:443/video/1','https://ok.ru/video/0','https://ok.ru/video/1/evil','https://ok.ru/video/%31','javascript:alert(1)'])
def test_rejects_unsafe_embed(value):assert embed_url(value) is None


def seed(system):
    system.supabase_service.table('contenido').insert({'id':421,'tipo':'biblico','fuente':'okru','titulo':'Pablo',
        'playback_url':'https://ok.ru/video/10328454335072','disponible':True,'descarga':'https://www.mediafire.com/file/manual/file'}).execute()


def test_okru_auth_entitlement_and_downloads(client,system):
    seed(system)
    for path in ['/api/playback/421','/api/download/421']:
        r=send(client,path,method='GET');assert r.status_code==401 and r.json['code']=='auth_required' and 'url' not in r.json
    register(client)
    for path in ['/api/playback/421','/api/download/421']:
        r=send(client,path,method='GET');assert r.status_code==403 and r.json['code']=='membership_required' and 'url' not in r.json
    member=system.app.test_client();session=tg_login(member)
    r=send(member,'/api/playback/421',{},session.json['csrf_token'])
    assert r.status_code==200 and r.json['url']==embed_url('https://ok.ru/video/10328454335072')
    assert 'https://ok.ru' in r.headers['Content-Security-Policy']
    assert send(member,'/api/download/421',method='GET').json['url']=='https://www.mediafire.com/file/manual/file'
    public=send(client,'/api/contenido',{'id':421}).json
    assert 'playback_url' not in str(public) and '10328454335072' not in str(public)


def test_okru_episode_ownership_and_private_urls(client,system):
    seed(system);db=system.supabase_service
    db.table('temporadas').insert({'id':421,'contenido_id':421,'numero':1}).execute()
    db.table('episodios').insert({'id':421,'temporada_id':421,'numero':1,'disponible':True,'playback_url':'https://ok.ru/video/123','descarga':'https://www.mediafire.com/file/chapter/file'}).execute()
    register(client)
    assert send(client,'/api/episode-download/421/421',method='GET').json['code']=='membership_required'
    member=system.app.test_client();tg_login(member)
    assert send(member,'/api/playback/421?episodio_id=421',method='GET').json['url']==embed_url('https://ok.ru/video/123')
    assert send(member,'/api/episode-download/421/421',method='GET').status_code==200
    assert send(member,'/api/playback/421?episodio_id=999',method='GET').status_code==404
    db.table('temporadas').update({'contenido_id':999}).eq('id',421).execute()
    assert send(member,'/api/playback/421?episodio_id=421',method='GET').status_code==404
