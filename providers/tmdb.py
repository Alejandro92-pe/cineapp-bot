"""Spanish-Mexico metadata; official Latin trailers before Spain fallback."""
import re
import math
import requests


def tmdb_rating(metadata):
    value = metadata.get('vote_average')
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10 else None


class TMDBClient:
    BASE = 'https://api.themoviedb.org/3'

    def __init__(self, api_key, transport=None, timeout=(5,12)):
        self.api_key = api_key
        self.transport = transport or requests.Session()
        self.timeout = timeout

    def get(self, path, params=None):
        if not re.fullmatch(r'/(movie|tv)/[0-9]+(?:/season/[0-9]+|/videos)?', path):
            raise ValueError('Ruta de metadatos no permitida.')
        query = {**(params or {}), 'language':'es-MX', 'api_key':self.api_key}
        response = self.transport.get(self.BASE+path, params=query, timeout=self.timeout, allow_redirects=False)
        if response.status_code != 200: raise ValueError('TMDB no respondió correctamente.')
        return response.json()

    def discover_movies(self, year, page=1):
        if type(year) is not int or not 2000 <= year <= 2100 or type(page) is not int or not 1 <= page <= 3:
            raise ValueError('Selección fuera de los límites permitidos.')
        response = self.transport.get(self.BASE+'/discover/movie', params={
            'api_key':self.api_key,'language':'es-MX','primary_release_year':year,
            'include_adult':'false','sort_by':'popularity.desc','vote_count.gte':100,'page':page},
            timeout=self.timeout,allow_redirects=False)
        if response.status_code != 200: raise ValueError('TMDB no respondió correctamente.')
        return response.json()

    def search_movie(self,title,year):
        return self.search_title('movie',title,year)

    def search_title(self,media,title,year):
        if media not in ('movie','tv') or not isinstance(title,str) or not 1<=len(title)<=500 or not str(year).isdigit():
            raise ValueError('Título o año inválidos.')
        response=self.transport.get(self.BASE+'/search/'+media,params={'api_key':self.api_key,
            'language':'es-MX','query':title,('primary_release_year' if media=='movie' else 'first_air_date_year'):str(year),'include_adult':'false','page':1},
            timeout=self.timeout,allow_redirects=False)
        if response.status_code!=200:raise ValueError('TMDB no respondió correctamente.')
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
