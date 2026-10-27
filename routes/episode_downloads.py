"""Private, entitlement-checked downloads for one episode at a time."""
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request, g


def episode_download_routes(database, entitlement, safe_url):
    bp = Blueprint('episode_downloads', __name__)

    def find(content_id, episode_id):
        content = database.table('contenido').select('id,tipo').eq('id',content_id).eq('disponible',True).execute().data
        episode = database.table('episodios').select('id,temporada_id,descarga,provider_download_url').eq('id',episode_id).eq('disponible',True).execute().data
        if not content or content[0]['tipo'] not in ('serie','anime','biblico') or not episode: return None
        season = database.table('temporadas').select('id').eq('id',episode[0]['temporada_id']).eq('contenido_id',content_id).execute().data
        return episode[0] if season else None

    @bp.get('/api/episode-download/<int:content_id>/<int:episode_id>')
    def download(content_id,episode_id):
        if not entitlement(g.identity['account'].get('telegram_id')):
            return jsonify(error='Tu acceso no está activo o ha vencido.',code='membership_required'),403
        episode=find(content_id,episode_id)
        link=safe_url(episode.get('descarga') or episode.get('provider_download_url')) if episode else None
        if not link:return jsonify(error='Este episodio no tiene una descarga disponible.'),404
        return jsonify(url=link,host=urlsplit(link).hostname)

    @bp.route('/api/admin/episode-download/<int:content_id>/<int:episode_id>',methods=['GET','POST'])
    def edit(content_id,episode_id):
        episode=find(content_id,episode_id)
        if not episode:return jsonify(error='Episodio no disponible.'),404
        if request.method=='GET':return jsonify(url=episode.get('descarga') or '')
        value=request.json.get('url')
        if not isinstance(value,str) or len(value)>4096:return jsonify(error='Enlace inválido.'),400
        value=value.strip()
        link=safe_url(value) if value else None
        if value and not link:return jsonify(error='Usa un enlace HTTPS válido de descarga.'),400
        database.table('episodios').update({'descarga':link}).eq('id',episode_id).execute()
        if getattr(database,'preview_downloads_path',None) is not None:
            from services.preview_downloads import save
            save(database,content_id,episode_id,link)
        return jsonify(success=True,has_download=bool(link or episode.get('provider_download_url')))

    return bp
