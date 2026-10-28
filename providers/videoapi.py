"""Public VideoAPI embeds. No credentials, catalog writes or provider HTML."""
from providers.vimeus import integer
from collections import OrderedDict
import threading
import time
import requests
from urllib.parse import urlencode

KINDS = {'pelicula': 'movie', 'serie': 'tv', 'anime': 'anime'}


def embed_path(kind, tmdb, season=None, episode=None):
    if kind not in KINDS:
        raise ValueError('Tipo no permitido.')
    path = f"/e/{KINDS[kind]}/{integer(tmdb, 1)}"
    if kind != 'pelicula':
        path += f'/{integer(season)}/{integer(episode, 1)}'
    return path


def embed_url(kind, tmdb, season=None, episode=None):
    # Public presentation options only. Never request paid/VIP or ad controls.
    return 'https://videoapi.la' + embed_path(kind, tmdb, season, episode) + '?' + urlencode({
        'primary_color': '78b7fb', 'secondary_color': '111d30', 'icon_color': 'edf5ff'})


class Availability:
    """Bounded per-worker cache; a failure falls back without retrying on the request."""
    def __init__(self, get=requests.get, clock=time.monotonic):
        self.get, self.clock = get, clock
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def __call__(self, kind, tmdb, season=None, episode=None):
        path = embed_path(kind, tmdb, season, episode)
        with self.lock:
            cached = self.cache.get(path)
            if cached and cached[0] > self.clock():
                self.cache.move_to_end(path)
                return cached[1]
        available, ttl = None, 30
        try:
            response = self.get('https://videoapi.la/api/v1/public/exists/' + path[3:],
                                timeout=(1.5, 2), allow_redirects=False)
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict) and type(payload.get('exists')) is bool:
                    if payload['exists'] and payload.get('path') == path:
                        available, ttl = True, 1800
                    elif not payload['exists'] and payload.get('path') is None:
                        available, ttl = False, 120
        except (requests.RequestException, ValueError):
            pass
        with self.lock:
            self.cache[path] = (self.clock() + ttl, available)
            self.cache.move_to_end(path)
            while len(self.cache) > 2048:
                self.cache.popitem(last=False)
        return available


available = Availability()
