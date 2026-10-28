"""Owner-only editor. Global security supplies owner authentication and CSRF."""
from flask import Blueprint, request, jsonify, current_app
from providers.vimeus import ImportFailure, integer
from services.okru_editor import document, apply_local


def okru_routes(database):
    bp=Blueprint('okru_editor',__name__)

    @bp.get('/api/admin/okru')
    def catalog():
        try:page=integer(request.args.get('page','1'),1)
        except ImportFailure as error:return jsonify(error=str(error)),400
        if page>1000:return jsonify(error='Página inválida.'),400
        query=database.table('contenido').select('id,titulo,disponible',count='exact').eq('tipo','biblico')
        text=request.args.get('q','').strip()[:100]
        if text:query=query.ilike('titulo','%'+text+'%')
        rows=query.order('id',desc=True).limit(25).offset((page-1)*25).execute()
        return jsonify(data=rows.data,page=page,has_next=page*25<rows.count)

    @bp.route('/api/admin/okru/<int:content_id>',methods=['GET','POST'])
    def edit(content_id):
        content=database.table('contenido').select('id,titulo,playback_url').eq('id',content_id).eq('tipo','biblico').execute().data
        if not content:return jsonify(error='Bíblico no disponible.'),404
        if request.method=='POST':
            try:
                doc=document(content_id,request.json)
                result=apply_local(database,doc) if current_app.config['SECURITY_LOCAL'] else database.rpc('guardar_okru',{'documento':doc}).execute().data
                return jsonify(result)
            except ImportFailure as error:return jsonify(error=str(error)),400
        try:
            page=integer(request.args.get('page','1'),1)
            number=integer(request.args.get('season','1'))
            if page>2000 or number>9999:raise ImportFailure('Numeración fuera de rango.')
        except ImportFailure as error:return jsonify(error=str(error)),400
        seasons=database.table('temporadas').select('id,numero,nombre,episodios').eq('contenido_id',content_id).order('numero').execute().data
        selected=[s for s in seasons if s['numero']==number]
        if len(selected)>1:return jsonify(error='Hay temporadas duplicadas; revísalas antes de editar.'),409
        rows=database.table('episodios').select('id,numero,titulo,playback_url,disponible',count='exact').eq('temporada_id',selected[0]['id']).order('numero').limit(50).offset((page-1)*50).execute() if selected else None
        return jsonify(content=content[0],seasons=seasons,episodes=rows.data if rows else [],page=page,has_next=bool(rows and page*50<rows.count))
    return bp
