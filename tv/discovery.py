"""Compact facet index; full cards are fetched only for the requested page."""
import time
import unicodedata
from collections import Counter
from threading import RLock
from tv.metadata import FIELDS, INDEX_FIELDS, public_item, resolve_formats


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').lower()) if unicodedata.category(c) != 'Mn').strip()


GENRES = {
    'accion': ('Acción', ('accion','action','action & adventure')),
    'aventura': ('Aventura', ('aventura','adventure','action & adventure')),
    'drama': ('Drama', ('drama',)),
    'comedia': ('Comedia', ('comedia','comedy')),
    'terror': ('Terror', ('terror','horror')),
    'suspenso': ('Suspenso', ('suspense','suspenso','thriller')),
    'misterio': ('Misterio', ('misterio','mystery')),
    'fantasia': ('Fantasía', ('fantasia','fantasy','sci-fi & fantasy')),
    'ciencia-ficcion': ('Ciencia ficción', ('ciencia ficcion','science fiction','sci-fi & fantasy')),
    'crimen': ('Crimen', ('crimen','crime')),
    'romance': ('Romance', ('romance',)),
    'familia': ('En familia', ('familia','family','kids')),
    'animacion': ('Animación', ('animacion','animation','anime')),
    'historia': ('Historia', ('historia','history')),
    'documental': ('Documentales', ('documental','documentary')),
    'belica': ('Guerra y política', ('belica','guerra','war','war & politics')),
    'western': ('Western', ('western',)),
    'novela': ('Telenovelas', ('soap','telenovela')),
}


def genre_keys(row):
    tokens = {normalized(g) for g in (row.get('genero') or '').split(',')}
    return {key for key, (_, aliases) in GENRES.items() if tokens.intersection(aliases)}


class Discovery:
    def __init__(self, database, clock=time.monotonic):
        self.db, self.clock, self.cache, self.lock = database, clock, {}, RLock()
        self.category_locks = {}

    def _rows(self, kind):
        with self.lock:
            category_lock = self.category_locks.setdefault(kind, RLock())
        # Slow refreshes in one collection must not block another collection.
        with category_lock:
            cached = self.cache.get(kind)
            if cached and cached[0] > self.clock(): return cached[1]
            rows = []
            for offset in range(0, 10000, 500):
                q = self.db.table('contenido').select(INDEX_FIELDS).eq('disponible', True)
                if kind: q = q.eq('tipo', kind)
                batch = q.order('id', desc=True).limit(500).offset(offset).execute().data
                rows.extend(batch)
                if len(batch) < 500: break
            else: raise ValueError('El catálogo supera el límite de esta vista local.')
            enriched = [{**row, '_genres':genre_keys(row)} for row in resolve_formats(self.db,rows)]
            self.cache[kind] = (self.clock()+300, enriched)
            return enriched

    def browse(self, kind=None, query='', genre='', order='recent', form='', page=1):
        rows = self._rows(kind)
        counts = Counter(key for row in rows for key in row['_genres'])
        filters = [{'id':key, 'label':GENRES[key][0], 'count':count} for key,count in counts.most_common()]
        formats = [{'id':key,'label':label,'count':sum(r['format']==key for r in rows)} for key,label in [('movies','Películas'),('series','Series bíblicas')]] if kind=='biblico' else []
        matching = [r for r in rows if (not genre or genre in r['_genres']) and (not form or r['format']==form) and (not query or normalized(query) in normalized(r['titulo']))]
        if order == 'rating': matching.sort(key=lambda r: (float(r.get('rating') or 0),r['id']), reverse=True)
        elif order == 'az': matching.sort(key=lambda r: (normalized(r['titulo']),r['id']))
        else: matching.sort(key=lambda r:r['id'], reverse=True)
        total = len(matching)
        page = min(page, max(1, (total+11)//12))
        feature = next((r for r in matching if r.get('backdrop_url')), matching[0] if matching else None)
        selected = matching[(page-1)*12:page*12]
        ids = list(dict.fromkeys([r['id'] for r in selected]+([feature['id']] if feature else [])))
        cards = self.db.table('contenido').select(FIELDS).eq('disponible',True).in_('id',ids).limit(13).execute().data if ids else []
        # Reuse the bounded index's season evidence; fresh TMDB metadata on the
        # cards can still identify a series imported during the index's TTL.
        formats_by_id = {r['id']:r['format'] for r in matching}
        by_id = {r['id']:public_item({**r,'format':formats_by_id[r['id']]}) for r in cards}
        return {'items':[by_id[r['id']] for r in selected if r['id'] in by_id],
                'featured':by_id.get(feature['id']) if feature else None,'total':total,'collection_total':len(rows),
                'genres':filters,'formats':formats,'page':page,'pages':max(1,(total+11)//12),'has_next':page*12<total}
