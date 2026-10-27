from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from security import CATALOG_FIELDS
from services.profiles import AVATARS, Profiles


def profile_routes(database, store):
    bp = Blueprint('profile', __name__)
    profiles = Profiles(store)

    def public_rows(ids):
        if not ids:
            return []
        rows = database.table('contenido').select('*').eq('disponible', True).in_('id', ids).execute().data
        by_id = {r['id']: {**{k: v for k, v in r.items() if k in CATALOG_FIELDS},
                          'has_download': bool(r.get('descarga'))} for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def payload(account_id):
        data = profiles.snapshot(account_id)
        data['account_id'] = account_id
        data['items'] = public_rows(data['saved_ids'])
        return jsonify(data)

    @bp.route('/api/profile', methods=['GET', 'POST'])
    def profile():
        account_id = g.identity['account']['id']
        try:
            if request.method == 'GET':
                return payload(account_id)
            if not store.allow_attempt('profile:' + account_id, maximum=120, seconds=60):
                return jsonify(error='Espera un momento antes de volver a guardar.'), 429
            body = request.get_json()
            action = body.get('action')
            if action in ('avatar', 'bootstrap'):
                avatar = body.get('avatar', 'tg')
                if not isinstance(avatar, str) or avatar not in AVATARS:
                    return jsonify(error='Elige uno de los avatares disponibles.'), 400
                items = []
                if action == 'bootstrap':
                    ids = body.get('saved_ids', [])
                    if not isinstance(ids, list) or len(ids) > 200 or any(type(i) is not int or not 0 < i < 2147483648 for i in ids):
                        return jsonify(error='La lista de títulos no es válida.'), 400
                    items = [(r['id'], True) for r in public_rows(list(dict.fromkeys(ids)))]
                profiles.mutate(account_id, avatar=avatar, items=items, bootstrap=action == 'bootstrap')
            elif action == 'saved':
                content_id, saved = body.get('content_id'), body.get('saved')
                if type(content_id) is not int or not 0 < content_id < 2147483648 or type(saved) is not bool:
                    return jsonify(error='El título o la selección no son válidos.'), 400
                if saved and not public_rows([content_id]):
                    return jsonify(error='Este título ya no está disponible.'), 404
                profiles.mutate(account_id, items=[(content_id, saved)])
            else:
                return jsonify(error='Selecciona una acción válida.'), 400
            return payload(account_id)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except SQLAlchemyError:
            return jsonify(error='No pudimos sincronizar tu cuenta. Inténtalo de nuevo en un momento.'), 503

    return bp
