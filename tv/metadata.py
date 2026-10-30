"""Public TV metadata: thematic category is independent of playback format."""
FIELDS = 'id,titulo,tipo,tmdb_media,año,genero,sinopsis,imagen_url,backdrop_url,rating'
INDEX_FIELDS = 'id,titulo,tipo,tmdb_media,genero,rating,backdrop_url'


def content_format(row, has_seasons=None):
    has_seasons = row.get('format') == 'series' if has_seasons is None else has_seasons
    if row.get('tipo') in ('serie','anime') or row.get('tmdb_media') == 'tv' or has_seasons:
        return 'series'
    if row.get('tipo') == 'pelicula' or row.get('tmdb_media') == 'movie':
        return 'movies'
    return 'unknown'


def resolve_formats(database, rows):
    """Resolve legacy biblical rows in batches, without a query per card.

    TMDB's TV marker works even before seasons are imported. Historical rows
    can use existing seasons without depending on an undocumented content FK.
    """
    ids = [r['id'] for r in rows if r.get('tipo') == 'biblico' and r.get('tmdb_media') != 'tv']
    serial_ids = set()
    for start in range(0, len(ids), 100):
        for offset in range(0, 10000, 500):
            batch = (database.table('temporadas').select('id,contenido_id')
                     .in_('contenido_id', ids[start:start+100]).order('id')
                     .limit(500).offset(offset).execute().data)
            serial_ids.update(s['contenido_id'] for s in batch)
            if len(batch) < 500:
                break
        else:
            raise ValueError('Demasiadas temporadas en esta colección.')
    return [{**r, 'format':content_format(r, r['id'] in serial_ids)} for r in rows]


def public_item(row, has_seasons=None):
    return {**{k:row.get(k) for k in FIELDS.split(',')}, 'format':content_format(row,has_seasons)}
