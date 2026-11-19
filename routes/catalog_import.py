"""Unified admin entry; local mode reads prepared snapshots, never production."""
import json,subprocess,sys,time
from pathlib import Path
from flask import Blueprint,current_app,jsonify,request
from providers.vimeus import ImportFailure,integer
from services.metadata_import import build_metadata,apply_local
from services.vimeus_import import import_title,ImportRepository


def catalog_import_routes(db,provider,get,videoapi_import=None,vimeus_alive=lambda:True):
    bp=Blueprint('catalog_import',__name__)
    @bp.post('/api/admin/catalog/import')
    def import_catalog():
        try:
            data=request.get_json()
            if not isinstance(data,dict):raise ImportFailure('Completa el formulario de importación.')
            tmdb=integer(data.get('tmdb_id'),1);kind=data.get('tipo')
            if kind not in ('pelicula','serie','anime','biblico_pelicula','biblico_serie'):raise ImportFailure('Tipo de título inválido.')
            if kind in ('serie','anime'):
                if not current_app.config['SECURITY_LOCAL']:
                    reason='Vimeus está caído.'
                    if vimeus_alive():
                        try:return jsonify(import_title(provider,ImportRepository(db),tmdb,kind,get))
                        except ImportFailure as error:
                            if not videoapi_import:raise
                            reason=f'Vimeus: {error}'
                    elif not videoapi_import:raise ImportFailure('Vimeus no está disponible y VideoAPI no está activado para importar.')
                    # Same title, chapters confirmed one by one in VideoAPI. Existing downloads are kept.
                    result=videoapi_import(kind,tmdb)
                    if result.get('busy'):return jsonify(error=result['message'],code='busy'),409
                    if result.get('pending'):
                        done=f"{result['checked']} de {result['total']}" if result.get('total') else str(result['checked'])
                        return jsonify(pending=True,provider='videoapi',reason=reason,checked=result['checked'],total=result.get('total'),
                            titulo=result.get('titulo'),message=f'Importando desde VideoAPI: {done} capítulos revisados. Pulsa Importar otra vez para continuar; si no, el importador automático la terminará.'),202
                    return jsonify({**result,'provider':'videoapi','reason':reason})
            if current_app.config['SECURITY_LOCAL']:
                path=Path(current_app.config.get('METADATA_SNAPSHOT_DIR','.local/tmdb-imports'))/f'{kind}-{tmdb}.json'
                if current_app.config.get('ALLOW_PREVIEW_METADATA_FETCH') and (not path.exists() or time.time()-path.stat().st_mtime>86400):
                    root=Path(__file__).resolve().parents[1]
                    try:
                        process=subprocess.run([sys.executable,str(root/'scripts/prepare_tmdb_import.py'),str(tmdb),'--kind',kind],cwd=root,capture_output=True,timeout=190)
                        if process.returncode:raise ImportFailure('No se pudo completar la lectura del proveedor. No se guardaron cambios; intenta de nuevo.')
                    except subprocess.TimeoutExpired:raise ImportFailure('La consulta tardó demasiado. No se guardaron cambios.') from None
                if not path.exists():raise ImportFailure('Este título aún no tiene una ficha preparada para la vista previa.')
                doc=json.loads(path.read_text(encoding='utf-8'))
                if kind in ('serie','anime'):
                    from services.manual_vimeus import apply_saved
                    return jsonify(apply_saved(db,doc))
            else:
                if not get:raise ImportFailure('Configura la clave de TMDB para importar.')
                doc=build_metadata(get,tmdb,kind)
            if data.get('content_id'):doc['content_id']=integer(data['content_id'],1)
            result=apply_local(db,doc) if current_app.config['SECURITY_LOCAL'] else db.rpc('importar_metadatos',{'documento':doc}).execute().data
            return jsonify(result)
        except ImportFailure as e:return jsonify(error=str(e)),422
    return bp
