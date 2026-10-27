"""TMDB supplies descriptions and episode structure, never playable video URLs."""
import copy
import json
from providers.vimeus import ImportFailure, integer
from providers.tmdb import trailer_url, tmdb_rating
from services.vimeus_import import image_url


def build_metadata(get, tmdb_id, kind):
    tmdb_id=integer(tmdb_id,1)
    if kind not in ('pelicula','biblico_pelicula','biblico_serie'):
        raise ImportFailure('Selecciona película o bíblico.')
    media='tv' if kind=='biblico_serie' else 'movie'
    meta=get(f'/{media}/{tmdb_id}')
    if integer(meta.get('id'),1)!=tmdb_id:raise ImportFailure('TMDB devolvió otro título.')
    c={'tipo':'pelicula' if kind=='pelicula' else 'biblico','tmdb_id':tmdb_id,'tmdb_media':media,
       'titulo':meta.get('name' if media=='tv' else 'title') or f'TMDB {tmdb_id}',
       'sinopsis':meta.get('overview') or '', 'imagen_url':image_url(meta.get('poster_path')),
       'backdrop_url':image_url(meta.get('backdrop_path')).replace('/w500','/w1280'),
       'genero':', '.join(g['name'] for g in meta.get('genres',[]) if g.get('name')),
       'rating':tmdb_rating(meta)}
    year=str(meta.get('first_air_date' if media=='tv' else 'release_date') or '')[:4]
    if year.isdigit():c['año']=int(year)
    trailer=trailer_url(get,media,tmdb_id)
    if trailer:c['trailer_url']=trailer
    seasons=[];seen=set();total=0
    for entry in meta.get('seasons',[]) if media=='tv' else []:
        number=integer(entry.get('season_number'))
        if number in seen or len(seen)>=100:raise ImportFailure('Listado de temporadas inválido.')
        seen.add(number)
        details=get(f'/tv/{tmdb_id}/season/{number}')
        if integer(details.get('season_number'))!=number:raise ImportFailure('Temporada incorrecta.')
        episodes=details.get('episodes')
        if not isinstance(episodes,list):raise ImportFailure('Listado de capítulos incompleto.')
        if entry.get('episode_count') is not None and len(episodes)!=integer(entry['episode_count']):
            raise ImportFailure('TMDB cambió durante la consulta. Reintenta para importar la temporada completa.')
        numbers=set();normalized=[]
        for e in episodes:
            n=integer(e.get('episode_number'),1)
            if n in numbers or integer(e.get('season_number'))!=number:raise ImportFailure('Capítulos duplicados o de otra temporada.')
            numbers.add(n);total+=1
            if total>5000:raise ImportFailure('El título supera 5.000 capítulos.')
            normalized.append({'numero':n,'titulo':e.get('name') or f'Episodio {n}',
              'sinopsis':e.get('overview') or '', 'imagen_url':image_url(e.get('still_path')),
              'duracion':e.get('runtime') if isinstance(e.get('runtime'),int) and e['runtime']>0 else None})
        seasons.append({'numero':number,'nombre':details.get('name') or f'Temporada {number}',
          'poster_url':image_url(details.get('poster_path')),'descripcion':details.get('overview') or '',
          'capitulos':sorted(normalized,key=lambda e:e['numero'])})
    if media=='tv' and not seasons:raise ImportFailure('TMDB no tiene temporadas para este título.')
    return {'contenido':c,'temporadas':sorted(seasons,key=lambda s:s['numero'])}


def apply_local(db,doc,persist=True):
    with db.lock:
        before=copy.deepcopy(db.rows)
        try:
            c=doc['contenido'];target=doc.get('content_id')
            same=db.table('contenido').select('*').eq('tipo',c['tipo']).eq('tmdb_id',c['tmdb_id']).execute().data
            if len(same)>1:raise ImportFailure('Hay fichas duplicadas; selecciona y revisa el catálogo.')
            if target:
                rows=db.table('contenido').select('*').eq('id',target).eq('tipo',c['tipo']).execute().data
                if not rows or (same and same[0]['id']!=target):raise ImportFailure('La ficha elegida no coincide o ya existe otra con ese TMDB.')
                if rows[0].get('tmdb_id') not in (None,c['tmdb_id']):raise ImportFailure('Esta ficha pertenece a otro TMDB.')
            else:rows=same
            if rows:
                item=rows[0]
                if item.get('tmdb_media') not in (None,c['tmdb_media']):raise ImportFailure('El ID pertenece a otro tipo de título en TMDB.')
                # Keep editorial names and every playback/download field intact.
                values={k:v for k,v in c.items() if v and not item.get(k)}
                values.update(tmdb_id=c['tmdb_id'],tmdb_media=c['tmdb_media'])
                if c.get('rating') is not None:values['rating']=c['rating']
                db.table('contenido').update(values).eq('id',item['id']).execute()
            else:
                item=db.table('contenido').insert({**c,'fuente':'vimeus' if c['tipo']=='pelicula' else 'okru',
                    'disponible':True,'destacado':False,'playback_unverified':True}).execute().data[0]
            cid=item['id'];created=updated=total=0
            for s in doc['temporadas']:
                rows=db.table('temporadas').select('*').eq('contenido_id',cid).eq('numero',s['numero']).execute().data
                if len(rows)>1:raise ImportFailure('Hay temporadas duplicadas.')
                season=rows[0] if rows else db.table('temporadas').insert({**{k:v for k,v in s.items() if k!='capitulos'},'contenido_id':cid,'episodios':0}).execute().data[0]
                for e in s['capitulos']:
                    rows=db.table('episodios').select('*').eq('temporada_id',season['id']).eq('numero',e['numero']).execute().data
                    if len(rows)>1:raise ImportFailure('Hay capítulos duplicados.')
                    if rows:
                        values={k:v for k,v in e.items() if v and not rows[0].get(k)}
                        if rows[0].get('titulo')==f"Episodio {e['numero']}":values['titulo']=e['titulo']
                        db.table('episodios').update(values).eq('id',rows[0]['id']).execute();updated+=1
                    else:
                        db.table('episodios').insert({**e,'temporada_id':season['id'],'disponible':True}).execute();created+=1
                    total+=1
                count=len(db.table('episodios').select('id').eq('temporada_id',season['id']).eq('disponible',True).execute().data)
                db.table('temporadas').update({'episodios':count}).eq('id',season['id']).execute()
            path=getattr(db,'metadata_edits_path',None)
            if persist and path:
                saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                saved[f"{c['tipo']}:{c['tmdb_id']}"]=doc
                temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8');temp.replace(path)
            return {'success':True,'contenido_id':cid,'titulo':item['titulo'],'temporadas':len(doc['temporadas']),
                    'episodios':total,'creados':created,'actualizados':updated,'retirados':0,'metadata_only':c['tipo']=='biblico'}
        except Exception:
            db.rows=before
            raise


def restore(db,path):
    db.metadata_edits_path=path
    if path.exists():
        for doc in json.loads(path.read_text(encoding='utf-8')).values():apply_local(db,doc,persist=False)
