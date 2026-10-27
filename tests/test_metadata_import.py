import copy,json
import pytest
from conftest import send,owner_login,register
from services.metadata_import import build_metadata,apply_local,restore
from providers.vimeus import ImportFailure


def lookup(path,params=None):
    if path.endswith('/videos'):return {'results':[]}
    if '/season/' in path:return {'season_number':1,'episodes':[{'season_number':1,'episode_number':1,'name':'Comienzo'},{'season_number':1,'episode_number':2,'name':'La promesa'}]}
    return {'id':66825,'name':'Josué','title':'Película','seasons':[{'season_number':1,'episode_count':2}]}


def test_metadata_preserves_existing_links_visibility_and_manual_episodes(system,tmp_path):
    db=system.supabase_service;doc=build_metadata(lookup,66825,'biblico_serie');doc['content_id']=208
    db.table('contenido').insert({'id':208,'tipo':'biblico','titulo':'Título editorial','fuente':'okru','descarga':'https://mediafire.com/manual','playback_url':'https://ok.ru/video/123','disponible':True}).execute()
    db.table('temporadas').insert({'id':5,'contenido_id':208,'numero':1,'nombre':'Mi temporada'}).execute()
    db.table('episodios').insert({'id':50,'temporada_id':5,'numero':1,'titulo':'Mi capítulo','disponible':False,'descarga':'https://mediafire.com/episode','playback_url':'https://ok.ru/video/456'}).execute()
    db.table('episodios').insert({'id':51,'temporada_id':5,'numero':9,'titulo':'Especial manual','disponible':True}).execute()
    db.metadata_edits_path=tmp_path/'edits.json';before=copy.deepcopy(db.rows)
    result=apply_local(db,doc);assert result['creados']==1
    assert apply_local(db,doc)['creados']==0
    c=db.table('contenido').select('*').eq('id',208).execute().data[0]
    assert c['titulo']=='Título editorial' and c['descarga']=='https://mediafire.com/manual' and c['fuente']=='okru'
    ep=db.table('episodios').select('*').eq('id',50).execute().data[0]
    assert ep['titulo']=='Mi capítulo' and ep['disponible'] is False and ep['playback_url'].endswith('/456') and ep['descarga'].endswith('/episode')
    assert db.table('episodios').select('*').eq('id',51).execute().data[0]['disponible']
    db.rows=before;restore(db,db.metadata_edits_path);restore(db,db.metadata_edits_path)
    assert len(db.table('episodios').select('*').eq('temporada_id',5).execute().data)==3


def test_incomplete_season_aborts_without_partial_catalog(system):
    def broken(path,params=None):
        data=lookup(path,params)
        if '/season/' in path:data['episodes'].pop()
        return data
    before=copy.deepcopy(system.supabase_service.rows)
    with pytest.raises(ImportFailure):build_metadata(broken,66825,'biblico_serie')
    assert system.supabase_service.rows==before


def test_duplicate_target_or_wrong_media_rolls_back(system):
    db=system.supabase_service;doc=build_metadata(lookup,66825,'biblico_serie')
    db.table('contenido').insert({'id':208,'tipo':'biblico','tmdb_id':66825,'tmdb_media':'movie','titulo':'Existing'}).execute()
    before=copy.deepcopy(db.rows)
    with pytest.raises(ImportFailure):apply_local(db,doc)
    assert db.rows==before


def test_disk_failure_rolls_back(system,tmp_path,monkeypatch):
    from pathlib import Path
    db=system.supabase_service;db.metadata_edits_path=tmp_path/'edits.json';before=copy.deepcopy(db.rows)
    def fail(*a,**kw):raise OSError('disk')
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):apply_local(db,build_metadata(lookup,66825,'biblico_serie'))
    assert db.rows==before


def test_owner_route_csrf_persistence_and_public_no_video(client,system,tmp_path,monkeypatch):
    doc=build_metadata(lookup,66825,'biblico_serie');(tmp_path/'biblico_serie-66825.json').write_text(json.dumps(doc))
    monkeypatch.setitem(system.app.config,'METADATA_SNAPSHOT_DIR',str(tmp_path))
    body={'tipo':'biblico_serie','tmdb_id':66825}
    assert send(client,'/api/admin/catalog/import',body).status_code==401
    user=register(client)
    assert send(client,'/api/admin/catalog/import',body,user.json['csrf_token']).status_code==403
    csrf=owner_login(client).json['csrf_token']
    assert send(client,'/api/admin/catalog/import',body).status_code==403
    r=send(client,'/api/admin/catalog/import',body,csrf);assert r.status_code==200 and r.json['episodios']==2
    cid=r.json['contenido_id'];sid=system.supabase_service.table('temporadas').select('id').eq('contenido_id',cid).execute().data[0]['id']
    public=send(client,f'/api/episodios/{cid}/{sid}',method='GET').json
    assert all(e['has_playback'] is False for e in public['episodios'])
    assert 'playback_url' not in json.dumps(public)


def test_movies_share_the_unified_importer(client,system,tmp_path,monkeypatch):
    doc=build_metadata(lookup,66825,'pelicula');assert doc['temporadas']==[] and doc['contenido']['tipo']=='pelicula'
    (tmp_path/'pelicula-66825.json').write_text(json.dumps(doc))
    monkeypatch.setitem(system.app.config,'METADATA_SNAPSHOT_DIR',str(tmp_path))
    csrf=owner_login(client).json['csrf_token']
    response=send(client,'/api/admin/catalog/import',{'tipo':'pelicula','tmdb_id':66825},csrf)
    assert response.status_code==200 and response.json['episodios']==0
    assert send(client,'/api/admin/catalog/import',{'tipo':'pelicula','tmdb_id':66825},csrf).json['contenido_id']==response.json['contenido_id']


def test_preview_preparation_is_bounded_and_reuses_complete_cache(client,system,tmp_path,monkeypatch):
    from types import SimpleNamespace
    calls=[]
    def prepare(command,**kwargs):
        calls.append(command);assert kwargs['timeout']==190 and not kwargs.get('shell')
        (tmp_path/'pelicula-66825.json').write_text(json.dumps(build_metadata(lookup,66825,'pelicula')))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('routes.catalog_import.subprocess.run',prepare)
    monkeypatch.setitem(system.app.config,'METADATA_SNAPSHOT_DIR',str(tmp_path))
    monkeypatch.setitem(system.app.config,'ALLOW_PREVIEW_METADATA_FETCH',True)
    csrf=owner_login(client).json['csrf_token']
    for _ in range(2):assert send(client,'/api/admin/catalog/import',{'tipo':'pelicula','tmdb_id':66825},csrf).status_code==200
    assert len(calls)==1 and calls[0][-3:]==['66825','--kind','pelicula']


def test_saved_vimeus_import_restores_without_duplicate_episodes(system,tmp_path):
    from services.manual_vimeus import apply_saved,restore as restore_vimeus
    from services.vimeus_import import build_manifest
    db=system.supabase_service;db.manual_vimeus_path=tmp_path/'manual.json'
    doc=build_manifest(system.vimeus_provider,900101,'serie')
    before=copy.deepcopy(db.rows);result=apply_saved(db,doc[0]);db.rows=before
    restore_vimeus(db,db.manual_vimeus_path);restore_vimeus(db,db.manual_vimeus_path)
    assert len(db.rows['episodios'])==result['episodios']


def test_download_restore_keeps_old_key_when_tmdb_is_linked(system,tmp_path):
    from services.preview_downloads import restore as restore_downloads
    db=system.supabase_service;result=apply_local(db,build_metadata(lookup,66825,'biblico_serie'))
    cid=result['contenido_id'];path=tmp_path/'downloads.json'
    path.write_text(json.dumps({f'biblico:{cid}:1:1':'https://mediafire.com/manual'}))
    restore_downloads(db,path)
    assert db.rows['episodios'][0]['descarga']=='https://mediafire.com/manual'
