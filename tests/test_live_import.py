import json
from types import SimpleNamespace
import pytest
from providers.vimeus import VimeusClient, ImportFailure
from providers.tmdb import TMDBClient, trailer_url
from services.vimeus_import import build_manifest, provider_download, ImportRepository, import_title
from services.local_vimeus import DemoVimeus
from conftest import send, tg_login


def compact_row(number,kind='series'):
    return {'tmdb_id':42,'parent_type':kind,'show_title':'Example','season':'1','episode':str(number),
            'download_url':f'https://vimeus.com/d/{kind}?tmdb=42&se=1&ep={number}&view_key=test'}


class Compact:
    def __init__(self,duplicate=False):self.duplicate=duplicate
    def get(self,url,**kwargs):
        page=kwargs['params']['page']
        rows=[compact_row(n) for n in (range(1,76) if page==1 else [1 if self.duplicate else 76])]
        return SimpleNamespace(status_code=200,json=lambda:{'error':False,'data':{'pages':2,'result':rows}})


def test_real_compact_format_accepts_variable_page_size_without_inventing_ids():
    result=VimeusClient('key',Compact()).episodes(42,'serie')
    assert len(result)==76 and all(r['id'] is None for r in result)
    assert result[-1]['episode']==76 and result[0]['title']=='Example'


def test_compact_overlap_rejected_before_writing():
    with pytest.raises(ImportFailure,match='duplicados'):VimeusClient('key',Compact(True)).episodes(42,'serie')


@pytest.mark.parametrize('kind,path',[('serie','series'),('anime','animes')])
def test_download_validates_title_episode_and_media(kind,path):
    row=compact_row(3,path);row.update(season=1,episode=3)
    assert provider_download(row,42,kind)==row['download_url']
    assert provider_download(row,99,kind) is None
    row['download_url']=row['download_url'].replace('ep=3','ep=4')
    assert provider_download(row,42,kind) is None


def test_download_prefers_manual_and_never_leaks_provider_url(client,system):
    result=import_title(DemoVimeus(),ImportRepository(system.supabase_service),900202,'anime')
    ep=system.supabase_service.rows['episodios'][0]
    provider='https://vimeus.com/d/animes?tmdb=900202&se=1&ep=1'
    system.supabase_service.table('episodios').update({'provider_download_url':provider}).eq('id',ep['id']).execute()
    metadata=send(client,f"/api/episodios/{result['contenido_id']}/{ep['temporada_id']}",method='GET')
    assert metadata.json['episodios'][0]['has_download']
    assert 'provider_download_url' not in metadata.json['episodios'][0]
    tg_login(client);url=f"/api/episode-download/{result['contenido_id']}/{ep['id']}"
    assert send(client,url,method='GET').json['url']==provider
    system.supabase_service.table('episodios').update({'descarga':'https://mediafire.com/file/manual/file'}).eq('id',ep['id']).execute()
    assert 'mediafire' in send(client,url,method='GET').json['url']


def test_tmdb_uses_mexico_language_and_does_not_mutate_callers_params():
    class Transport:
        def get(self,url,**kwargs):
            assert kwargs['params']['language']=='es-MX'
            assert kwargs['allow_redirects'] is False
            return SimpleNamespace(status_code=200,json=lambda:{'title':'Mexico'})
    params={'language':'es-ES'}
    assert TMDBClient('key',Transport()).get('/movie/42',params)['title']=='Mexico'
    assert params['language']=='es-ES'


def test_trailer_prefers_official_mexico_then_latin_then_spain_and_rejects_bad_keys():
    def video(country,key,**kw):return {'iso_3166_1':country,'iso_639_1':'es','site':'YouTube','key':key,'type':'Trailer','official':True,**kw}
    rows=[video('ES','spain123456'),video('AR','argentina12'),video('MX','mexico12345'),video('MX','bad-key')]
    assert trailer_url(lambda *a:{'results':rows},'movie',42).endswith('mexico12345')
    assert trailer_url(lambda *a:{'results':[rows[0],rows[1]]},'tv',42).endswith('argentina12')
    assert trailer_url(lambda *a:{'results':[rows[0],rows[3]]},'tv',42).endswith('spain123456')
    assert trailer_url(lambda *a:{'results':[rows[3]]},'tv',42)==''


def test_preview_download_survives_restart(tmp_path):
    from local_support import LocalDatabase
    from services.preview_downloads import restore,save
    db=LocalDatabase();result=import_title(DemoVimeus(),ImportRepository(db),900202,'anime')
    restore(db,tmp_path/'downloads.json');ep=db.rows['episodios'][0]
    save(db,result['contenido_id'],ep['id'],'https://mediafire.com/file/manual/file')
    replacement=LocalDatabase();import_title(DemoVimeus(),ImportRepository(replacement),900202,'anime');restore(replacement,tmp_path/'downloads.json')
    assert replacement.rows['episodios'][0]['descarga']=='https://mediafire.com/file/manual/file'
