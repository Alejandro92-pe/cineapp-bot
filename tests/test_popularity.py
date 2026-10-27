from datetime import datetime, timezone
from conftest import send, tg_login, owner_login, register
from services.popularity import local_day
from services.vimeus_import import import_title, ImportRepository
from services.local_vimeus import DemoVimeus


def anime(system):
    result=import_title(DemoVimeus(),ImportRepository(system.supabase_service),900202,'anime')
    return result['contenido_id'],system.supabase_service.rows['episodios'][0]['id']


def test_rank_requires_authorized_post_and_deduplicates_title_per_day(client,system):
    cid,ep=anime(system);path=f'/api/playback/{cid}?episodio_id={ep}'
    assert send(client,path,{}).status_code==401
    user=register(client)
    assert send(client,path,{},user.json['csrf_token']).status_code==403
    member=system.app.test_client();auth=tg_login(member)
    assert send(member,path,method='GET').status_code==200
    assert system.popularity_store.ranking()==[]
    assert send(member,path,{}).status_code==403
    assert send(member,path,{},auth.json['csrf_token']).status_code==200
    assert send(member,path,{},auth.json['csrf_token']).status_code==200
    assert system.popularity_store.ranking()==[{'content_id':cid,'score':1}]
    result=send(client,'/api/top10',method='GET').json
    assert result['mode']=='ranked' and result['data'][0]['id']==cid
    assert not ({'descarga','enlace_canal','account_id','score'} & result['data'][0].keys())


def test_invalid_episode_and_admin_do_not_change_ranking(client,system):
    cid,ep=anime(system);auth=tg_login(client)
    assert send(client,f'/api/playback/{cid}?episodio_id=999999',{},auth.json['csrf_token']).status_code==404
    admin=system.app.test_client();owner=owner_login(admin)
    import time
    from billing.schema import access
    with system.security_store.engine.begin() as c:
        c.execute(access.insert().values(account_id=system.security_store.account(telegram_id=5824989040)['id'],expires_at=time.time()+3600))
    assert send(admin,f'/api/playback/{cid}?episodio_id={ep}',{},owner.json['csrf_token']).status_code==200
    assert system.popularity_store.ranking()==[]
    assert send(client,'/api/top10',method='GET').json['mode']=='discovery'


def test_window_and_hidden_titles_and_persistence(client,system):
    cid,ep=anime(system);auth=tg_login(client)
    account=system.security_store.account(telegram_id=900000001)['id'];today=local_day()
    store=system.popularity_store
    store.record(account,1,today-7);store.record(account,cid,today-6);store.record(account,cid,today)
    from services.popularity import Popularity
    assert Popularity(system.security_store).ranking()==[{'content_id':cid,'score':2}]
    system.supabase_service.table('contenido').update({'disponible':False}).eq('id',cid).execute()
    result=send(client,'/api/top10',method='GET').json
    assert result['mode']=='discovery' and cid not in [r['id'] for r in result['data']]
    assert local_day(datetime(2026,10,26,4,59,tzinfo=timezone.utc))+1==local_day(datetime(2026,10,26,5,0,tzinfo=timezone.utc))

def test_ranking_changes_with_distinct_members_and_limits_to_ten(client,system):
    db=system.supabase_service
    template=db.rows['contenido'][0]
    db.rows['contenido']=[{**template,'id':n,'titulo':f'Title {n}'} for n in range(1,13)]
    members=[system.security_store.create_account(f'Test {n}',email=f'rank{n}@example.test')['id'] for n in range(3)]
    for cid in range(1,13):system.popularity_store.record(members[0],cid)
    assert [r['id'] for r in send(client,'/api/top10',method='GET').json['data']]==list(range(1,11))
    for member in members[1:]:system.popularity_store.record(member,12)
    ranked=send(client,'/api/top10',method='GET').json
    assert ranked['mode']=='ranked' and len(ranked['data'])==10 and ranked['data'][0]['id']==12
