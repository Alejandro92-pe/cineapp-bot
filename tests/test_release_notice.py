import re
from sqlalchemy import event
from conftest import ORIGIN
from tv.app import create_app  # Register TV tables before the shared test DB is built.

def test_public_version_and_html_match_without_account_database(client, system):
    def forbidden(*args, **kwargs): raise AssertionError('Version must not read private data')
    event.listen(system.security_store.engine, 'before_cursor_execute', forbidden)
    try:
        response=client.get('/version.json',base_url=ORIGIN)
        assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
        build=response.json['version'];assert re.fullmatch('[a-f0-9]{20}',build)
        assert list(response.json)==['version']
        for path in ('/', '/cuenta'):
            html=client.get(path,base_url=ORIGIN)
            assert f'name="qh-release" content="{build}"' in html.text
            assert '/static/updates/notice.js' in html.text
            assert html.headers['Cache-Control']=='no-store'
            reload=client.get(path,base_url=ORIGIN,headers={'If-Modified-Since':'Tue, 01 Jan 2030 00:00:00 GMT'})
            assert reload.status_code==200 and f'content="{build}"' in reload.text
    finally:event.remove(system.security_store.engine, 'before_cursor_execute', forbidden)

def test_tv_notice_uses_its_own_public_routes(system):
    tv=create_app(system.supabase_service,system.security_store,ORIGIN).test_client()
    build=tv.get('/tv/version.json',base_url=ORIGIN).json['version']
    response=tv.get('/tv',base_url=ORIGIN)
    assert f'content="{build}"' in response.text
    assert '/tv/update-notice.js' in response.text
    assert tv.get('/tv/update-notice.js',base_url=ORIGIN).status_code==200
    assert tv.get('/tv/update-notice.css',base_url=ORIGIN).status_code==200

def test_biblical_discovery_batches_seasons_and_reuses_cache():
    from local_support import LocalDatabase
    from tv.discovery import Discovery
    db=LocalDatabase();seed=db.rows['contenido'][0]
    db.rows['contenido']=[{**seed,'id':i,'tipo':'biblico'} for i in range(1,29)]
    db.rows['temporadas']=[{'id':i,'contenido_id':2,'numero':i} for i in range(1,502)]+[{'id':502,'contenido_id':28,'numero':1}]
    calls=[];table=db.table
    def counted(name):
        q=table(name);execute=q.execute
        def run():calls.append(name);return execute()
        q.execute=run;return q
    db.table=counted;clock=[0];d=Discovery(db,lambda:clock[0])
    result=d.browse('biblico',form='series')
    assert {r['id'] for r in result['items']}=={2,28}
    assert calls==['contenido','temporadas','temporadas']
    clock[0]=299;d.browse('biblico');assert len(calls)==3
    clock[0]=301;d.browse('biblico');assert len(calls)==6
