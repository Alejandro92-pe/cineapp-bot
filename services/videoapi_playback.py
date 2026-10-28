"""Choose an existing title's playback source without changing catalog records."""
from providers.videoapi import KINDS, available, embed_url
from providers.vimeus import integer


def eligible(app, item):
    if not app.config.get('VIDEOAPI_ENABLED') or item.get('fuente') != 'vimeus' or item.get('tipo') not in KINDS:
        return False
    try:
        integer(item.get('tmdb_id'), 1)
    except (ValueError, TypeError):
        return False
    pilot = app.config.get('VIDEOAPI_PILOT') if app.config.get('SECURITY_LOCAL') else None
    if pilot is not None:
        row = pilot.get(str(item.get('id')), {})
        return str(row.get('tmdb_id')) == str(item.get('tmdb_id')) and row.get('tipo') == item.get('tipo')
    return True


def playback(app, database, item, episode_id):
    """None requests the existing Vimeus path; invalid episode IDs never fall back."""
    if not eligible(app, item):
        return {'error': 'Reproductor no disponible para este título.'}, 404
    season = episode = None
    if item['tipo'] in ('serie', 'anime'):
        if episode_id is None:
            return None  # Legacy titles can still use Vimeus' episode selector.
        episodes = database.table('episodios').select('temporada_id,numero').eq('id', episode_id).eq('disponible', True).execute().data
        seasons = database.table('temporadas').select('numero').eq('id', episodes[0]['temporada_id']).eq('contenido_id', item['id']).execute().data if episodes else []
        if not seasons:
            return {'error': 'Este capítulo no pertenece al título o ya no está disponible.'}, 404
        season, episode = seasons[0]['numero'], episodes[0]['numero']
    pilot = app.config.get('VIDEOAPI_PILOT') if app.config.get('SECURITY_LOCAL') else None
    if pilot is not None:
        exists = item['tipo'] == 'pelicula' or [season, episode] in pilot[str(item['id'])].get('episodes', [])
    else:
        exists = available(item['tipo'], item['tmdb_id'], season, episode)
    if not exists:
        return None
    return {'url': embed_url(item['tipo'], item['tmdb_id'], season, episode), 'embed': True, 'provider': 'videoapi'}, 200
