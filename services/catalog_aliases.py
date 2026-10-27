"""Persistent redirects for reviewed series-part consolidation."""


def resolve_alias(database, content_id):
    local = getattr(database, 'catalog_aliases', None)
    if isinstance(local, dict):
        return local.get(content_id)
    rows = database.table('catalog_aliases').select('content_id,start_season').eq('original_id', content_id).execute().data
    return {'id': rows[0]['content_id'], 'start_season': rows[0]['start_season']} if rows else None
