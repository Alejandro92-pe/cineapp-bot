"""Strict adapter for VideoAPI's documented public catalog and existence API."""
from providers.vimeus import ImportFailure, integer
from providers.videoapi import embed_path

RESOURCES = {'movies': ('movies', 'movie'), 'series': ('tvshows', 'tv'), 'animes': ('anime', 'anime')}


class VideoAPICatalog:
    def __init__(self, transport, page_size=24):
        self.transport, self.page_size = transport, integer(page_size, 1)
        if self.page_size > 24:
            raise ValueError('Páginas de hasta 24 títulos.')

    def get(self, path, params=None):
        response = self.transport.get('https://videoapi.la/api/v1/public/' + path,
                                      params=params or {}, allow_redirects=False)
        if response.status_code != 200:
            raise ImportFailure('VideoAPI no respondió con un catálogo válido.')
        data = response.json()
        if not isinstance(data, dict):
            raise ImportFailure('Respuesta de VideoAPI incompleta.')
        return data

    def page(self, resource, page=1):
        feed, kind = RESOURCES[resource]
        data = self.get('wordpress/' + feed + '/latest', {'page': integer(page, 1), 'limit': self.page_size})
        rows, pagination = data.get('items'), data.get('pagination', {})
        if (data.get('status') != 'ok' or not isinstance(rows, list) or len(rows) > self.page_size
                or pagination.get('page') != page or type(pagination.get('has_next')) is not bool
                or (not rows and pagination['has_next'])):
            raise ImportFailure('Página incompleta; no se avanza el catálogo.')
        seen, clean = set(), []
        for row in rows:
            tmdb = integer(row.get('tmdb_id'), 1)
            if row.get('type') != kind or tmdb in seen:
                raise ImportFailure('Tipo o identidad de catálogo incorrectos.')
            seen.add(tmdb)
            # Never persist remote iframe HTML, arbitrary URLs or unbounded fields.
            clean.append({'tmdb_id': tmdb, 'title': str(row.get('title') or '')[:300]})
        return clean, {'has_next': pagination['has_next']}

    def exists(self, kind, tmdb, season=None, episode=None):
        path = embed_path(kind, tmdb, season, episode)
        data = self.get('exists/' + path[3:])
        if data.get('exists') is True and data.get('path') == path:
            return True
        if data.get('exists') is False and data.get('path') is None:
            return False
        raise ImportFailure('Disponibilidad no confirmada; no se omite el capítulo.')
