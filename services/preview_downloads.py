"""Keep local manual download edits across preview restarts, keyed by title/episode."""
import json


def key(database,content_id,episode_id):
    content=next(c for c in database.rows['contenido'] if c['id']==content_id)
    episode=next(e for e in database.rows['episodios'] if e['id']==episode_id)
    season=next(s for s in database.rows['temporadas'] if s['id']==episode['temporada_id'])
    return f"{content['tipo']}:{content.get('tmdb_id') or content_id}:{season['numero']}:{episode['numero']}"


def restore(database,path):
    database.preview_downloads_path=path
    saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for season in database.rows['temporadas']:
        for episode in database.rows['episodios']:
            if episode['temporada_id']==season['id']:
                identity=key(database,season['contenido_id'],episode['id'])
                content=next(c for c in database.rows['contenido'] if c['id']==season['contenido_id'])
                legacy=f"{content['tipo']}:{content['id']}:{season['numero']}:{episode['numero']}"
                if identity in saved:episode['descarga']=saved[identity]
                elif legacy in saved:episode['descarga']=saved[legacy]


def save(database,content_id,episode_id,value):
    path=getattr(database,'preview_downloads_path',None)
    if path is None:return
    with database.lock:
        saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        saved[key(database,content_id,episode_id)]=value
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved),encoding='utf-8');temp.replace(path)
