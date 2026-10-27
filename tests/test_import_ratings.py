import copy
import math
import pytest
from local_support import LocalDatabase
from services.local_vimeus import apply_local, DemoVimeus
from services.vimeus_import import build_manifest
from services.metadata_import import build_metadata, apply_local as apply_metadata
from providers.tmdb import tmdb_rating


@pytest.mark.parametrize('value', [None, '8.5', True, -1, 11, math.nan, math.inf])
def test_invalid_scores_are_not_invented(value):
    assert tmdb_rating({'vote_average': value}) is None


def test_series_rating_survives_create_update_and_metadata_outage():
    provider = DemoVimeus()
    def get(path, params=None):
        return {'name': 'Serie', 'vote_average': 8.432}
    doc, _ = build_manifest(provider, 900101, 'serie', get)
    assert doc['contenido']['rating'] == 8.432
    db = LocalDatabase()
    cid = apply_local(db, doc)['contenido_id']
    db.table('contenido').update({'titulo': 'Nombre editorial', 'descarga': 'https://www.mediafire.com/file/manual'}).eq('id', cid).execute()
    episode = db.rows['episodios'][0]
    episode['descarga'] = 'https://www.mediafire.com/file/episode'
    episode_before = copy.deepcopy(episode)
    doc['contenido']['rating'] = 8.6
    apply_local(db, doc)
    item = db.table('contenido').select('*').eq('id', cid).execute().data[0]
    assert item['rating'] == 8.6 and item['titulo'] == 'Nombre editorial'
    assert item['descarga'].endswith('/manual') and db.rows['episodios'][0] == episode_before
    def offline(*args, **kwargs):
        raise ValueError('offline')
    without, _ = build_manifest(provider, 900101, 'serie', offline)
    assert 'rating' not in without['contenido']
    apply_local(db, without)
    assert db.table('contenido').select('*').eq('id', cid).execute().data[0]['rating'] == 8.6


def test_biblical_movie_rating_refresh_preserves_manual_links():
    db = LocalDatabase()
    doc = build_metadata(lambda *args: {'id': 123, 'title': 'Bíblico', 'vote_average': 7.2}, 123, 'biblico_pelicula')
    cid = apply_metadata(db, doc, persist=False)['contenido_id']
    db.table('contenido').update({'playback_url': 'https://ok.ru/video/123', 'descarga': 'https://www.mediafire.com/file/manual'}).eq('id', cid).execute()
    doc['contenido']['rating'] = 7.6
    apply_metadata(db, doc, persist=False)
    row = db.table('contenido').select('*').eq('id', cid).execute().data[0]
    assert row['rating'] == 7.6 and row['playback_url'] == 'https://ok.ru/video/123' and row['descarga'].endswith('/manual')
