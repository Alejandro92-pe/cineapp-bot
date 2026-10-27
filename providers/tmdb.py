"""Spanish-Mexico metadata; official Latin trailers before Spain fallback."""
import re
import math
import requests


def tmdb_rating(metadata):
    value = metadata.get('vote_average')
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10 else None


class TMDBClient:
    BASE = 'https://api.themoviedb.org/3'

    def __init__(self, api_key, transport=None):
        self.api_key = api_key
        self.transport = transport or requests.Session()

    def get(self, path, params=None):
        if not re.fullmatch(r'/(movie|tv)/[0-9]+(?:/season/[0-9]+|/videos)?', path):
            raise ValueError('Ruta de metadatos no permitida.')
        query = {**(params or {}), 'language':'es-MX', 'api_key':self.api_key}
        response = self.transport.get(self.BASE+path, params=query, timeout=(5,12), allow_redirects=False)
        if response.status_code != 200: raise ValueError('TMDB no respondió correctamente.')
        return response.json()


def trailer_url(get, media, tmdb_id):
    try:
        rows = get(f'/{media}/{tmdb_id}/videos', {'include_video_language':'es'}).get('results', [])
    except Exception:
        return ''
    # User-approved order: Mexico, Latin America, then Spain.
    latin = {'MX','AR','BO','CL','CO','CR','CU','DO','EC','GT','HN','NI','PA','PE','PR','PY','SV','UY','VE'}
    valid = [r for r in rows if r.get('site')=='YouTube' and r.get('type')=='Trailer'
             and r.get('official') is True and r.get('iso_639_1')=='es'
             and r.get('iso_3166_1') in latin|{'ES'} and re.fullmatch(r'[A-Za-z0-9_-]{11}',str(r.get('key','')))]
    valid.sort(key=lambda r:(2 if r['iso_3166_1']=='MX' else 1 if r['iso_3166_1'] in latin else 0,str(r.get('published_at',''))),reverse=True)
    return 'https://www.youtube.com/watch?v='+valid[0]['key'] if valid else ''
