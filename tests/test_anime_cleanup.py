import copy
import pytest
from conftest import send
from services.catalog_cleanup import consolidate_preview
from services.episode_numbering import metadata_episode
from services.vimeus_import import build_manifest
from providers.vimeus import ImportFailure


def test_absolute_provider_numbers_map_only_metadata_and_keep_filler_downloads():
    class Provider:
        def episodes(self,*args):return [{'id':None,'title':'Naruto Shippuden','tmdb_id':31910,'season':3,'episode':number,
            'download_url':f'https://vimeus.com/d/animes?tmdb=31910&se=3&ep={number}'} for number in [56,57,58]]
    def metadata(path,*args):
        if '/season/' in path:return {'episodes':[{'episode_number':n,'name':f'Capítulo {53+n}'} for n in range(1,19)]}
        return {'name':'Naruto Shippuden'}
    manifest,_=build_manifest(Provider(),31910,'anime',metadata);episodes=manifest['temporadas'][0]['capitulos']
    assert [e['numero'] for e in episodes]==[56,57,58] # 57 and 58 are filler: intentionally retained.
    assert [e['titulo'] for e in episodes]==['Capítulo 56','Capítulo 57','Capítulo 58']
    assert episodes[1]['provider_download_url'].endswith('ep=57')
    assert metadata_episode(46260,2,1,{53,54,55})==53
    assert metadata_episode(46260,2,1,{1,2,3})==1
    assert metadata_episode(31910,2,33,{33,34,35})==33
    with pytest.raises(ImportFailure):metadata_episode(31910,2,1)


def setup_parts(db):
    db.rows['contenido']=[{'id':404,'tmdb_id':45782,'titulo':'Sword Art Online','tipo':'anime','disponible':True},
        *[{'id':i,'titulo':str(i),'tipo':'anime','disponible':True,'enlace_canal':'https://t.me/original/1'} for i in [405,406,407]]]
    db.rows['temporadas']=[{'id':n,'contenido_id':404,'numero':n,'episodios':12} for n in [1,2,3,4]]


def test_confirmed_parts_hide_duplicates_but_keep_original_records_and_deep_links(client,system):
    db=system.supabase_service;setup_parts(db);before=copy.deepcopy(db.rows['contenido'])
    consolidate_preview(db)
    assert len(db.rows['contenido'])==4 and len(db.catalog_merge_archive)==3
    for old in before[1:]:assert old in db.catalog_merge_archive
    assert [r['id'] for r in send(client,'/api/contenido',{'tipo':'anime'}).json['data']]==[404]
    for old,season in [(405,2),(406,3),(407,4)]:
        result=send(client,'/api/contenido',{'id':old}).json['data'][0]
        assert result['id']==404 and result['start_season']==season and 'enlace_canal' not in result


def test_no_merge_if_target_season_missing_or_unique_download_would_be_lost(system):
    db=system.supabase_service;setup_parts(db)
    db.rows['contenido'][1]['descarga']='https://mediafire.com/file/unique/file'
    db.rows['temporadas']=[s for s in db.rows['temporadas'] if s['numero']!=3]
    consolidate_preview(db)
    assert db.rows['contenido'][1]['disponible'] and db.rows['contenido'][2]['disponible']
    assert db.catalog_aliases=={407:{'id':404,'start_season':4}}
