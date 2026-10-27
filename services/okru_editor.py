"""Validated edits; local persistence never writes downloads or legacy links."""
import copy
import json
from providers.okru import embed_url
from providers.vimeus import ImportFailure, integer


def document(content_id, data):
    if not isinstance(data,dict):raise ImportFailure('Envía los campos del vídeo para guardar.')
    url=embed_url(data.get('url'))
    if not url:raise ImportFailure('Pega un enlace HTTPS de vídeo de OK.ru, no código HTML.')
    result={'content_id':integer(content_id,1),'url':url,'scope':data.get('scope')}
    if result['scope']=='episode':
        result.update(season=integer(data.get('season')),episode=integer(data.get('episode'),1))
        if result['season']>9999 or result['episode']>99999:raise ImportFailure('Numeración fuera de rango.')
        title=data.get('title','')
        if not isinstance(title,str) or len(title)>300:raise ImportFailure('El título admite hasta 300 caracteres.')
        result['title']=title.strip()
    elif result['scope']!='title':raise ImportFailure('Selecciona vídeo completo o episodio.')
    return result


def apply_local(db, doc, persist=True):
    with db.lock:
        before=copy.deepcopy(db.rows)
        try:
            content=db.table('contenido').select('*').eq('id',doc['content_id']).eq('tipo','biblico').execute().data
            if len(content)!=1:raise ImportFailure('Bíblico no disponible.')
            cid=doc['content_id'];eid=None
            if doc['scope']=='title':
                db.table('contenido').update({'playback_url':doc['url'],'fuente':'okru'}).eq('id',cid).execute()
            else:
                seasons=db.table('temporadas').select('*').eq('contenido_id',cid).eq('numero',doc['season']).execute().data
                if len(seasons)>1:raise ImportFailure('Hay temporadas duplicadas; revisa el catálogo antes de guardar.')
                if not seasons:
                    seasons=db.table('temporadas').insert({'contenido_id':cid,'numero':doc['season'],
                        'nombre':'Especiales' if doc['season']==0 else f"Temporada {doc['season']}",'episodios':0,
                        'poster_url':content[0].get('imagen_url') or '', 'descripcion':''}).execute().data
                sid=seasons[0]['id']
                episodes=db.table('episodios').select('*').eq('temporada_id',sid).eq('numero',doc['episode']).execute().data
                if len(episodes)>1:raise ImportFailure('Hay capítulos duplicados; revisa el catálogo antes de guardar.')
                values={'playback_url':doc['url']}
                if doc['title']:values['titulo']=doc['title']
                if episodes:
                    eid=episodes[0]['id'];db.table('episodios').update(values).eq('id',eid).execute()
                else:
                    eid=db.table('episodios').insert({'temporada_id':sid,'numero':doc['episode'],
                        'titulo':doc['title'] or f"Episodio {doc['episode']}",'disponible':True,
                        'sinopsis':'','imagen_url':'','vimeus_id':None,**values}).execute().data[0]['id']
                count=len(db.table('episodios').select('id').eq('temporada_id',sid).eq('disponible',True).execute().data)
                db.table('temporadas').update({'episodios':count}).eq('id',sid).execute()
                db.table('contenido').update({'fuente':'okru'}).eq('id',cid).execute()
            path=getattr(db,'okru_edits_path',None)
            if persist and path:
                saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                key=f"{cid}:title" if doc['scope']=='title' else f"{cid}:{doc['season']}:{doc['episode']}"
                saved[key]=dict(doc)
                if eid is not None:
                    saved[key]['title']=db.table('episodios').select('titulo').eq('id',eid).execute().data[0]['titulo']
                temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8');temp.replace(path)
            return {'content_id':cid,'episode_id':eid,'url':doc['url'],'success':True}
        except Exception:
            db.rows=before
            raise


def restore(db,path):
    db.okru_edits_path=path
    if not path.exists():return
    for raw in json.loads(path.read_text(encoding='utf-8')).values():
        if any(r['id']==raw['content_id'] and r.get('tipo')=='biblico' for r in db.rows['contenido']):
            apply_local(db,document(raw['content_id'],raw),persist=False)
