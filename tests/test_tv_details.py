import copy
from local_support import LocalDatabase
from tv.catalog import Catalog

def setup():
    db=LocalDatabase();base=db.rows['contenido'][0]
    db.rows['contenido']=[{**base,'id':1,'tipo':'pelicula','fuente':'vimeus','tmdb_id':22},
                         {**base,'id':2,'tipo':'serie','fuente':'vimeus','tmdb_id':20}]
    db.rows['temporadas']=[{'id':10,'contenido_id':2,'numero':1,'episodios':12}]
    db.rows['episodios']=[{'id':i,'temporada_id':10,'numero':i,'titulo':str(i),'disponible':True,'playback_url':'https://ok.ru/video/123456','descarga':'PRIVATE'} for i in range(1,13)]
    calls=[];original=db.table
    def table(name):
        query=original(name);execute=query.execute
        def run():calls.append(name);return execute()
        query.execute=run;return query
    db.table=table
    return db,Catalog(db),calls

def test_open_details_reuses_reads_and_delivers_only_first_six_public_episodes():
    db,catalog,calls=setup();before=copy.deepcopy(db.rows)
    catalog.titles('pelicula');catalog.titles('serie');calls.clear()
    movie=catalog.details(1);assert calls==['contenido','temporadas'] and movie['playable'];calls.clear()
    series=catalog.details(2);assert calls==['contenido','temporadas','episodios']
    initial=series['initial_episodes'];assert initial['season_id']==10 and len(initial['items'])==6 and initial['has_next'] and initial['total']==12
    assert series['first_episode']['id']==1 and series['playable']
    assert 'PRIVATE' not in str(series) and 'playback_url' not in str(series) and 'https://ok.ru' not in str(series)
    assert db.rows==before

def test_early_empty_season_and_specials_keep_episode_order_and_okru_links_private():
    db,catalog,_=setup();db.rows['contenido'][1]['fuente']='okru'
    db.rows['temporadas'] += [{'id':11,'contenido_id':2,'numero':0,'episodios':1},{'id':12,'contenido_id':2,'numero':-1,'episodios':0}]
    db.rows['episodios'].append({'id':20,'temporada_id':11,'numero':1,'disponible':True})
    result=catalog.details(2);assert result['first_episode']['id']==1 and result['playable']
    db.rows['contenido'][1]['disponible']=False
    assert catalog.details(2) is None and catalog.source(2,1) is None and catalog.episodes(2,10,1) is None

def test_saved_state_cannot_leak_through_recommendation_cache():
    _,catalog,_=setup();first=catalog.titles('serie');first['items'][0]['saved']=True
    assert 'saved' not in catalog.titles('serie')['items'][0]
