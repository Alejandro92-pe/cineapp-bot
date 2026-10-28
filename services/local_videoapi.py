"""Offline additive publisher used only by local previews/tests."""
import copy
from providers.vimeus import ImportFailure
from services.metadata_import import apply_local as metadata_apply


def apply_local(db, document):
    with db.lock:
        before = copy.deepcopy(db.rows)
        try:
            doc = copy.deepcopy(document); c = doc['contenido']
            kinds = ('pelicula',) if c['tmdb_media'] == 'movie' else ('serie', 'anime')
            rows = [r for r in db.rows['contenido'] if r.get('tmdb_id') == c['tmdb_id']
                    and (r['tipo'] in kinds or (r['tipo']=='biblico' and r.get('tmdb_media')==c['tmdb_media']))
                    and r['id'] not in getattr(db, 'catalog_aliases', {})]
            if len(rows)>1: raise ImportFailure('Identidad TMDB ambigua; requiere revisión.')
            if rows:
                c['tipo'] = rows[0]['tipo']
                doc['content_id'] = rows[0]['id']
            result = metadata_apply(db, doc, persist=False)
            cid = result['contenido_id']
            values = {'videoapi_kind': document['contenido']['tipo']}
            if not rows or rows[0].get('fuente') != 'okru':
                values.update(fuente='vimeus', playback_unverified=False)
            db.table('contenido').update(values).eq('id',cid).execute()
            for s in doc['temporadas']:
                sid=db.table('temporadas').select('id').eq('contenido_id',cid).eq('numero',s['numero']).execute().data[0]['id']
                for e in s['capitulos']:
                    db.table('episodios').update({'videoapi_available':True}).eq('temporada_id',sid).eq('numero',e['numero']).execute()
            return result
        except Exception:
            db.rows = before
            raise
