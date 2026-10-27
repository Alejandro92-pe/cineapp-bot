import copy
import json
from pathlib import Path
import pytest
from conftest import send,owner_login,register,tg_login
from services.okru_editor import restore

URL='https://ok.ru/video/10328454335072'


def seed(system,tmp_path):
    db=system.supabase_service
    db.okru_edits_path=tmp_path/'edits.json'
    db.table('contenido').insert({'id':421,'tipo':'biblico','titulo':'Bíblico de prueba','disponible':True,'fuente':'telegram',
        'descarga':'https://www.mediafire.com/file/manual/movie/file','enlace_canal':'https://t.me/legacy'}).execute()
    return db


def test_admin_only_and_csrf(client,system,tmp_path):
    seed(system,tmp_path)
    assert send(client,'/api/admin/okru',method='GET').status_code==403
    register(client)
    assert send(client,'/api/admin/okru/421',method='GET').status_code==403
    owner=owner_login(client)
    assert send(client,'/api/admin/okru/421',{'scope':'title','url':URL}).status_code==403
    assert send(client,'/api/admin/okru/421',{'scope':'title','url':URL},owner.json['csrf_token']).status_code==200


def test_title_and_episode_edits_keep_downloads_and_ids(client,system,tmp_path):
    db=seed(system,tmp_path);csrf=owner_login(client).json['csrf_token']
    before=copy.deepcopy(db.rows['contenido'][-1])
    assert send(client,'/api/admin/okru/421',{'scope':'title','url':URL},csrf).status_code==200
    payload={'scope':'episode','url':URL,'season':2,'episode':7,'title':'El comienzo'}
    result=send(client,'/api/admin/okru/421',payload,csrf);assert result.status_code==200
    eid=result.json['episode_id'];ep=db.table('episodios').select('*').eq('id',eid).execute().data[0]
    db.table('episodios').update({'descarga':'https://www.mediafire.com/file/manual/ep/file','provider_download_url':'https://vimeus.com/d/old','disponible':False}).eq('id',eid).execute()
    result=send(client,'/api/admin/okru/421',{**payload,'title':'','url':'https://ok.ru/video/123'},csrf)
    updated=db.table('episodios').select('*').eq('id',eid).execute().data[0]
    assert result.json['episode_id']==eid and len(db.rows['episodios'])==1
    assert updated['titulo']=='El comienzo' and updated['disponible'] is False
    assert updated['descarga'].endswith('/ep/file') and updated['provider_download_url']=='https://vimeus.com/d/old'
    content=db.table('contenido').select('*').eq('id',421).execute().data[0]
    assert content['descarga']==before['descarga'] and content['enlace_canal']==before['enlace_canal']


def test_persist_restore_idempotent_and_episode_playback(client,system,tmp_path):
    db=seed(system,tmp_path);original=copy.deepcopy(db.rows);csrf=owner_login(client).json['csrf_token']
    body={'scope':'episode','url':URL,'season':1,'episode':1,'title':'Primer capítulo'}
    assert send(client,'/api/admin/okru/421',body,csrf).status_code==200
    assert send(client,'/api/admin/okru/421',{**body,'title':''},csrf).status_code==200
    path=db.okru_edits_path;db.rows=original
    restore(db,path);restore(db,path)
    assert len(db.rows['episodios'])==1 and len(db.rows['temporadas'])==1
    ep=db.rows['episodios'][0];member=system.app.test_client();tg_login(member)
    assert ep['titulo']=='Primer capítulo'
    response=send(member,f'/api/playback/421?episodio_id={ep["id"]}',method='GET')
    assert response.status_code==200 and 'videoembed/10328454335072' in response.json['url']
    public=send(member,f'/api/episodios/421/{ep["temporada_id"]}',method='GET').json
    assert 'playback_url' not in json.dumps(public)


@pytest.mark.parametrize('patch',[{'url':'https://evil.test/video/1'},{'season':-1},{'episode':0},{'episode':True},{'title':'a'*301},{'scope':'other'}])
def test_invalid_edit_makes_no_changes(client,system,tmp_path,patch):
    db=seed(system,tmp_path);before=copy.deepcopy(db.rows);csrf=owner_login(client).json['csrf_token']
    response=send(client,'/api/admin/okru/421',{'scope':'episode','url':URL,'season':1,'episode':1,**patch},csrf)
    assert response.status_code==400 and db.rows==before and not db.okru_edits_path.exists()


def test_failed_local_persistence_rolls_back(client,system,tmp_path,monkeypatch):
    db=seed(system,tmp_path);before=copy.deepcopy(db.rows);csrf=owner_login(client).json['csrf_token']
    def fail(*a,**kw):raise OSError('disk')
    monkeypatch.setattr(Path,'write_text',fail)
    response=send(client,'/api/admin/okru/421',{'scope':'episode','url':URL,'season':1,'episode':1},csrf)
    assert response.status_code==503 and db.rows==before


def test_admin_catalog_search_pagination_and_episode_pages(client,system,tmp_path):
    db=seed(system,tmp_path);owner_login(client)
    for n in range(30):db.table('contenido').insert({'id':1000+n,'tipo':'biblico','titulo':f'Historia {n}','disponible':True}).execute()
    result=send(client,'/api/admin/okru?q=Historia',method='GET');assert len(result.json['data'])==25 and result.json['has_next']
    assert len(send(client,'/api/admin/okru?q=Historia&page=2',method='GET').json['data'])==5
    db.table('temporadas').insert({'id':50,'contenido_id':421,'numero':1}).execute()
    for n in range(1,53):db.table('episodios').insert({'temporada_id':50,'numero':n,'titulo':f'Capítulo {n}','disponible':True}).execute()
    first=send(client,'/api/admin/okru/421',method='GET').json
    assert len(first['episodes'])==50 and first['has_next']
    assert len(send(client,'/api/admin/okru/421?page=2',method='GET').json['episodes'])==2
    assert send(client,'/api/admin/okru/1',method='GET').status_code==404
