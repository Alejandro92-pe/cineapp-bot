"""Admin import and public episode metadata. Playback stays authenticated."""
from flask import Blueprint, jsonify, request
from providers.vimeus import ImportFailure, integer
from services.vimeus_import import ImportRepository, import_title


def create_vimeus_routes(database, provider, tmdb_get=None):
    bp = Blueprint("vimeus", __name__)
    repository = ImportRepository(database)

    @bp.post("/api/admin/vimeus/importar")
    def import_vimeus():
        data = request.get_json()
        try:
            result = import_title(provider, repository, data.get("tmdb_id"), data.get("tipo"), tmdb_get)
            return jsonify(result)
        except ImportFailure as exc:
            return jsonify(error=str(exc)), 422

    @bp.get("/api/admin/vimeus/catalogo")
    def catalog():
        kind = request.args.get("tipo", "serie")
        try:
            if kind not in ("pelicula", "serie", "anime"):
                raise ImportFailure("Selecciona película, serie o anime.")
            rows, pagination = provider.page({"pelicula":"movies","serie":"series","anime":"animes"}[kind], integer(request.args.get("page", "1"), 1))
            allowed = ("tmdb_id", "title", "total_seasons", "total_episodes")
            return jsonify(data=[{k: row.get(k) for k in allowed} for row in rows], pagination=pagination)
        except ImportFailure as exc:
            return jsonify(error=str(exc)), 422

    @bp.get("/api/episodios/<int:contenido_id>/<int:temporada_id>")
    def episodes(contenido_id, temporada_id):
        content = database.table("contenido").select("id,tipo,fuente").eq("id", contenido_id).eq("disponible", True).execute().data
        season = database.table("temporadas").select("id").eq("contenido_id", contenido_id).eq("id", temporada_id).execute().data
        if not content or not season:
            return jsonify(error="Temporada no disponible."), 404
        # Pagination also avoids Supabase's default 1,000-row response cap.
        try:
            page = integer(request.args.get("page", "1"), 1)
            page_size = integer(request.args.get("page_size", "50"), 1)
        except ImportFailure:
            return jsonify(error="Página inválida."), 400
        if page_size > 50 or (page-1)*page_size >= 5000:
            return jsonify(error="Página inválida."), 400
        # Resume directly on the saved episode's page, not by downloading every
        # previous page of a long anime. Only public metadata is returned here.
        if request.args.get('around'):
            try:
                episode_id = integer(request.args['around'], 1)
            except ImportFailure:
                return jsonify(error='Episodio inválido.'), 400
            target = database.table('episodios').select('numero').eq('id', episode_id).eq('temporada_id', temporada_id).eq('disponible', True).limit(1).execute().data
            if target:
                preceding = database.table('episodios').select('id', count='exact', head=True).eq('temporada_id', temporada_id).eq('disponible', True).lt('numero', target[0]['numero']).execute()
                page = preceding.count // page_size + 1
        rows = database.table("episodios").select("id,temporada_id,numero,titulo,sinopsis,imagen_url,duracion,descarga,provider_download_url,playback_url", count="exact").eq("temporada_id", temporada_id).eq("disponible", True).order("numero").range((page-1)*page_size, page*page_size-1).execute()
        public=[]
        for row in rows.data:
            item=dict(row);manual=item.pop('descarga',None);provider_link=item.pop('provider_download_url',None)
            link=item.pop('playback_url',None)
            item['has_download']=bool(manual or provider_link)
            if content[0].get('tipo')=='biblico':
                from providers.okru import embed_url
                item['has_playback']=bool(embed_url(link))
            public.append(item)
        return jsonify(episodios=public, page=page, has_next=page*page_size < rows.count, total=rows.count)

    return bp
