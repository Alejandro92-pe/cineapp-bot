import os
from conftest import send


def test_episode_pages_resume_directly_and_keep_links_private(client, system, monkeypatch):
    db=system.supabase_service
    db.rows['contenido']=[{'id':88,'tipo':'anime','fuente':'vimeus','disponible':True}]
    db.rows['temporadas']=[{'id':44,'contenido_id':88,'numero':1}]
    db.rows['episodios']=[{'id':i,'numero':i,'temporada_id':44,'disponible':True,'titulo':str(i),'descarga':'https://mediafire.com/private'} for i in range(1,221)]
    calls=[]
    monkeypatch.setattr(system.security_store,'session',lambda token:calls.append(token))
    first=send(client,'/api/episodios/88/44?page_size=12&page=1',method='GET').json
    assert len(first['episodios'])==12 and first['has_next'] and first['total']==220
    resume=send(client,'/api/episodios/88/44?page_size=12&around=180',method='GET').json
    assert resume['page']==15 and [e['id'] for e in resume['episodios']]==list(range(169,181))
    assert all(e['has_download'] and 'descarga' not in e for e in resume['episodios'])
    assert not calls
    for query in ('page_size=51','page_size=0','page_size=bad','around=bad'):
        assert send(client,'/api/episodios/88/44?'+query,method='GET').status_code==400
    assert send(client,'/api/episodios/99/44?page_size=12',method='GET').status_code==404


def test_webhook_reports_failure_instead_of_acknowledging(client, system, monkeypatch, caplog):
    headers={'X-Telegram-Bot-Api-Secret-Token':os.environ['TELEGRAM_WEBHOOK_SECRET']}
    calls=[]
    def fail(updates):
        calls.append(updates)
        raise RuntimeError('PRIVATE-TOKEN')
    monkeypatch.setattr(system.bot,'process_new_updates',fail)
    assert send(client,'/webhook/telegram',{'update_id':123},headers=headers).status_code==503
    assert 'PRIVATE-TOKEN' not in caplog.text
    monkeypatch.setattr(system.bot,'process_new_updates',lambda updates:calls.append(updates))
    assert send(client,'/webhook/telegram',{'update_id':123},headers=headers).status_code==200
    assert len(calls)==2
    assert send(client,'/webhook/telegram',{},headers=headers).status_code==400

def test_real_postgrest_transport_has_no_missing_episode_at_page_boundary(client, system, monkeypatch):
    import httpx
    from postgrest import SyncPostgrestClient
    rows=[{'id':i,'numero':i,'temporada_id':44,'disponible':True} for i in range(1,26)]
    def transport(request):
        table=request.url.path.rsplit('/',1)[-1]
        if table=='contenido': data=[{'id':88,'tipo':'anime','fuente':'vimeus'}]
        elif table=='temporadas': data=[{'id':44}]
        else:
            start=int(request.url.params.get('offset',0));size=int(request.url.params.get('limit',1000))
            if 'range' in request.headers:
                start,end=map(int,request.headers['range'].split('-'));size=end-start+1
            data=rows[start:start+size]
        return httpx.Response(200,json=data,headers={'Content-Range':f'0-{len(data)-1}/{len(rows)}'})
    rest=SyncPostgrestClient('https://db.example/rest/v1')
    rest.session=httpx.Client(base_url='https://db.example/rest/v1',transport=httpx.MockTransport(transport))
    monkeypatch.setattr(system.supabase_service,'table',rest.table)
    ids=[]
    for page in (1,2,3):
        result=send(client,f'/api/episodios/88/44?page_size=12&page={page}',method='GET').json
        ids.extend(e['id'] for e in result['episodios'])
    assert ids==list(range(1,26))
    rest.session.close()
