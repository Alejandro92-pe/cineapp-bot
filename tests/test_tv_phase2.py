"""Offline regressions: biblical format, bounded metadata and private saved state."""
import copy
import json

from local_support import LocalDatabase
from tv.catalog import Catalog
from tv.discovery import Discovery
from tv.metadata import resolve_formats


def biblical_database():
    db = LocalDatabase()
    base = {**db.rows['contenido'][0], 'tipo':'biblico', 'fuente':'okru',
            'playback_url':'https://ok.ru/video/123456', 'descarga':'PRIVATE-DOWNLOAD'}
    db.rows['contenido'] = [
        {**base, 'id':1, 'titulo':'Película bíblica', 'tmdb_media':'movie'},
        {**base, 'id':2, 'titulo':'Serie completa', 'tmdb_media':'tv'},
        {**base, 'id':3, 'titulo':'Serie en importación', 'tmdb_media':'tv'},
        {**base, 'id':4, 'titulo':'Serie histórica', 'tmdb_media':None},
        {**base, 'id':5, 'titulo':'Formato pendiente', 'tmdb_media':None},
    ]
    db.rows['temporadas'] = [
        {'id':20, 'contenido_id':2, 'numero':1, 'episodios':0},
        {'id':40, 'contenido_id':4, 'numero':1, 'episodios':0},
    ]
    db.rows['episodios'] = [{'id':n, 'temporada_id':20, 'numero':n, 'disponible':True,
                             'playback_url':'https://ok.ru/video/123456', 'descarga':'PRIVATE-DOWNLOAD'}
                            for n in range(1,9)]
    return db


def track(db):
    calls = []
    original = db.table
    def table(name):
        q = original(name)
        execute = q.execute
        def run():
            result = execute()
            calls.append({'table':name, 'columns':q.columns, 'rows':len(result.data),
                          'bytes':len(json.dumps(result.data).encode())})
            return result
        q.execute = run
        return q
    db.table = table
    return calls


def test_biblical_format_survives_all_card_paths_without_mutating_downloads():
    db = biblical_database()
    before = copy.deepcopy(db.rows)
    c = Catalog(db)
    expected = {1:'movies', 2:'series', 3:'series', 4:'series', 5:'unknown'}
    for cards in (c.titles('biblico')['items'], c.titles(search='')['items'],
                  c.saved_titles([1,2,3,4,5])['items'], Discovery(db).browse('biblico')['items'],
                  Discovery(db).browse(query='')['items']):
        assert {r['id']:r['format'] for r in cards} == expected
        assert all(r['tipo']=='biblico' for r in cards)
        assert 'PRIVATE' not in str(cards) and 'playback_url' not in str(cards)
    for cid, form in expected.items():
        assert c.item(cid)['format'] == form
        detail = c.details(cid)
        assert detail['item']['format'] == form and detail['episodic'] == (form=='series')
        assert {r['id']:r['format'] for r in detail['related']} == {i:f for i,f in expected.items() if i!=cid}
    assert c.details(1)['playable']
    assert c.details(2)['playable']
    assert not c.details(3)['playable'] and c.source(3) is None
    assert not c.details(4)['playable'] and c.source(4) is None
    assert db.rows == before


def test_importing_chapters_preserves_series_and_becomes_visible_without_rewriting_data():
    db = biblical_database()
    c = Catalog(db)
    clock = [0]
    d = Discovery(db, lambda:clock[0])
    assert d.browse('biblico', query='importacion')['items'][0]['format']=='series'
    assert not c.details(3)['playable']
    # Simulate the user's independent importer. No writes by TV itself.
    db.rows['temporadas'].append({'id':30,'contenido_id':3,'numero':1,'episodios':0})
    db.rows['episodios'].append({'id':30,'temporada_id':30,'numero':1,'disponible':True,
                                'playback_url':'https://ok.ru/video/987654','descarga':'MANUAL'})
    before = copy.deepcopy(db.rows)
    result = c.details(3)
    assert result['item']['format']=='series' and result['playable']
    assert result['seasons'][0]['has_episodes'] and result['seasons'][0]['episodios']==1
    assert result['initial_episodes']['items'][0]['id']==30
    assert c.source(3,30)['url']=='https://ok.ru/videoembed/987654?nochat=1'
    clock[0] = 301
    assert d.browse('biblico', form='series')['total']==3
    assert db.rows==before


def test_empty_seasons_need_one_availability_query_and_stale_counters_do_not_hide_episodes():
    db = biblical_database()
    db.rows['temporadas'] = [{'id':i,'contenido_id':3,'numero':i,'episodios':99} for i in range(1,11)]
    db.rows['episodios'] = [{'id':1,'temporada_id':1,'numero':1,'disponible':False}]
    calls = track(db)
    c = Catalog(db)
    c.titles('biblico')  # Same warm recommendations as the baseline.
    calls.clear()
    empty = c.details(3)
    assert [q['table'] for q in calls]==['contenido','temporadas']
    assert not empty['playable'] and all(not s['has_episodes'] for s in empty['seasons'])
    db.rows['temporadas'][-1]['episodios']=0
    db.rows['episodios'].append({'id':2,'temporada_id':10,'numero':1,'disponible':True,
                                'playback_url':'https://ok.ru/video/123456'})
    calls.clear()
    result = c.details(3)
    assert [q['table'] for q in calls]==['contenido','temporadas','episodios']
    assert result['first_episode']['id']==2 and result['playable']
    assert result['seasons'][-1]['episodios']==1 and result['seasons'][-1]['has_episodes']


def test_next_episode_skips_empty_seasons_without_scanning_each_one():
    db = biblical_database()
    db.rows['temporadas']=[{'id':i,'contenido_id':3,'numero':i,'episodios':0} for i in range(1,11)]
    db.rows['episodios']=[{'id':1,'temporada_id':1,'numero':1,'disponible':True},
                         {'id':2,'temporada_id':10,'numero':1,'titulo':'Diez','disponible':True}]
    calls=track(db)
    assert Catalog(db).next_episode(3,1)=={'id':2,'numero':1,'titulo':'Diez','season':10}
    assert len(calls)==4  # availability, current, remainder of current, next populated season


def test_category_fetches_compact_index_and_only_page_cards():
    db = LocalDatabase()
    base = db.rows['contenido'][0]
    db.rows['contenido']=[{**base,'id':i,'tipo':'anime','titulo':f'Acción {i}',
                           'sinopsis':'x'*2000,'backdrop_url':'/background','genero':'Action & Adventure'}
                          for i in range(1,1202)]
    before=copy.deepcopy(db.rows)
    calls=track(db)
    d=Discovery(db)
    first=d.browse('anime')
    assert len(first['items'])==12
    assert [q['rows'] for q in calls]==[500,500,201,12]
    assert all('sinopsis' not in q['columns'] and 'imagen_url' not in q['columns'] for q in calls[:-1])
    calls.clear()
    second=d.browse('anime',page=2)
    assert [q['rows'] for q in calls]==[13]  # 12 cards plus the shared featured title
    assert not ({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
    assert d.browse('anime',query='accion 1201',genre='aventura')['total']==1
    assert db.rows==before


def test_legacy_biblical_resolution_batches_titles_and_pages_seasons():
    db=biblical_database()
    base=db.rows['contenido'][-1]
    db.rows['contenido']=[{**base,'id':i} for i in range(1,102)]
    db.rows['temporadas']=[{'id':i,'contenido_id':1,'numero':i} for i in range(1,502)]
    db.rows['temporadas'].append({'id':502,'contenido_id':101,'numero':1})
    calls=track(db)
    result=resolve_formats(db,db.rows['contenido'])
    assert [r['id'] for r in result if r['format']=='series']==[1,101]
    assert [q['rows'] for q in calls]==[500,1,1]


def test_saved_lookup_is_one_scoped_read_and_respects_tombstones(system):
    from sqlalchemy import event
    from services.profiles import Profiles
    store=system.security_store
    a=store.create_account('A')['id'];b=store.create_account('B')['id']
    p=Profiles(store)
    p.mutate(a,avatar='fox',items=[(1,True),(2,False)])
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(store.engine,'before_cursor_execute',capture)
    try:
        assert p.is_saved(a,1)
        assert len(statements)==1 and 'profiles' not in statements[0]
        assert 'account_id' in statements[0] and 'content_id' in statements[0]
        assert not p.is_saved(a,2) and not p.is_saved(b,1)
    finally:
        event.remove(store.engine,'before_cursor_execute',capture)


def test_installed_postgrest_serializes_bounded_availability_embed():
    # SDK contract only; the test suite prohibits all external network traffic.
    from postgrest import SyncPostgrestClient
    with SyncPostgrestClient('http://127.0.0.1:9999') as db:
        q=(db.table('temporadas').select('id,available:episodios(id)')
           .eq('contenido_id',3).eq('available.disponible',True)
           .limit(1,foreign_table='available').order('numero').limit(100))
        assert q.params['select']=='id,available:episodios(id)'
        assert q.params['available.limit']=='1' and q.params['limit']=='100'
        assert q.params['contenido_id']=='eq.3'
        assert q.params['available.disponible'].lower()=='eq.true'
