"""TV-only discovery over a bounded, cached set of public catalog metadata."""
import time
import unicodedata
from collections import Counter
from threading import RLock
from tv.catalog import FIELDS


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

    def _rows(self, kind):
        with self.lock:
            cached = self.cache.get(kind)
            if cached and cached[0] > self.clock(): return cached[1]
            rows = []
            for offset in range(0, 10000, 500):
                q = self.db.table('contenido').select(FIELDS).eq('disponible', True)
                if kind: q = q.eq('tipo', kind)
                batch = q.order('id', desc=True).limit(500).offset(offset).execute().data
                rows.extend(batch)
                if len(batch) < 500: break
            else: raise ValueError('El catálogo supera el límite de esta vista local.')
            episodic = set()
            if kind == 'biblico':
                # Only 28 titles in this collection; no episode lists are loaded.
                for row in rows:
                    if self.db.table('temporadas').select('id').eq('contenido_id',row['id']).limit(1).execute().data:
                        episodic.add(row['id'])
            enriched = [{**row, 'format':'series' if row['id'] in episodic else 'movies', '_genres':genre_keys(row)} for row in rows]
            self.cache[kind] = (self.clock()+60, enriched)
            return enriched

    def browse(self, kind=None, query='', genre='', order='recent', form='', page=1):
        rows = self._rows(kind)
        counts = Counter(key for row in rows for key in row['_genres'])
        filters = [{'id':key, 'label':GENRES[key][0], 'count':count} for key,count in counts.most_common()]
        formats = [{'id':key,'label':label,'count':sum(r['format']==key for r in rows)} for key,label in [('movies','Películas'),('series','Por episodios')]] if kind=='biblico' else []
        matching = [r for r in rows if (not genre or genre in r['_genres']) and (not form or r['format']==form) and (not query or normalized(query) in normalized(r['titulo']))]
        if order == 'rating': matching.sort(key=lambda r: (float(r.get('rating') or 0),r['id']), reverse=True)
        elif order == 'az': matching.sort(key=lambda r: (normalized(r['titulo']),r['id']))
        else: matching.sort(key=lambda r:r['id'], reverse=True)
        total = len(matching)
        page = min(page, max(1, (total+11)//12))
        def public(row): return {k:v for k,v in row.items() if k != '_genres'}
        feature = next((r for r in matching if r.get('backdrop_url')), matching[0] if matching else None)
        return {'items':[public(r) for r in matching[(page-1)*12:page*12]],
                'featured':public(feature) if feature else None,'total':total,'collection_total':len(rows),
                'genres':filters,'formats':formats,'page':page,'pages':max(1,(total+11)//12),'has_next':page*12<total}
