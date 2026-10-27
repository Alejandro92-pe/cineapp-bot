from flask import Blueprint, jsonify
from security import CATALOG_FIELDS


def popularity_routes(database, popularity):
    bp = Blueprint('popularity', __name__)

    @bp.get('/api/top10')
    def top10():
        scores = popularity.ranking()
        items = []
        if scores:
            rows = database.table('contenido').select('*').eq('disponible',True).in_('id',[s['content_id'] for s in scores]).execute().data
            by_id = {r['id']:r for r in rows}
            items = [by_id[s['content_id']] for s in scores if s['content_id'] in by_id][:10]
        ranked = bool(items)
        if not ranked:
            items = database.table('contenido').select('*').eq('disponible',True).order('id',desc=True).limit(10).execute().data
        public = [{**{k:v for k,v in row.items() if k in CATALOG_FIELDS},'has_download':bool(row.get('descarga'))} for row in items]
        return jsonify(data=public,mode='ranked' if ranked else 'discovery',window_days=7,metric='authorized_player_opens')

    return bp
