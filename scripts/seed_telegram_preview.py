"""Apply an offline public snapshot and a one-time owner trial to the preview only."""
import json
import time
from pathlib import Path


def seed_preview(database, security_store):
    root = Path(__file__).resolve().parents[1]
    path = root/'.local/catalog-snapshot.json'
    if path.exists():
        rows = json.loads(path.read_text(encoding='utf-8'))
        bindings_path=root/'.local/anime-bindings.json'
        bindings=json.loads(bindings_path.read_text(encoding='utf-8')) if bindings_path.exists() else []
        for row in rows:
            row['tipo']=str(row.get('tipo','')).strip()
            row['fuente']=str(row.get('fuente') or '').strip()
            match=next((b for b in bindings if b['id']==row['id']),None)
            if match:row.update(tmdb_id=match['tmdb_id'],fuente='vimeus')
            # Only TMDB movies can switch directly to the Vimeus player. Episode
            # availability must come from Vimeus Listing, never guessed from TMDB.
            if row.get('tipo') == 'pelicula' and row.get('tmdb_id'):
                row['playback_unverified'] = str(row.get('fuente') or '').strip() != 'vimeus'
                row['fuente'] = 'vimeus'
            row['enlace_canal'] = None  # no channel invitations from this preview
        database.rows['contenido'] = rows
        database.rows['temporadas'] = []
        database.rows['episodios'] = []
        from services.local_vimeus import apply_local
        for snapshot in sorted((root/'.local/vimeus-manifests').glob('*.json')):
            manifest=json.loads(snapshot.read_text(encoding='utf-8'))
            result=apply_local(database,manifest)
            # Refresh imported descriptions in this local copy only; downloads remain intact.
            database.table('contenido').update(manifest['contenido']).eq('id',result['contenido_id']).execute()
        metadata_path=root/'.local/movie-metadata.json'
        if metadata_path.exists():
            for update in json.loads(metadata_path.read_text(encoding='utf-8')):
                database.table('contenido').update(update['metadata']).eq('id',update['id']).execute()
        from services.preview_downloads import restore
        from services.catalog_queue import completed_manifests
        for manifest in completed_manifests(root/'.local/import-queue.sqlite'):
            apply_local(database,manifest)
        restore(database,root/'.local/episode-downloads.json')
        from services.catalog_cleanup import consolidate_preview
        consolidate_preview(database)
        # Separate local test clip: never replace an existing biblical title or its downloads.
        if not any(r['id']==900421 for r in database.rows['contenido']):
            database.table('contenido').insert({'id':900421,'titulo':'Final | Pablo El Apóstol | Audio Latino',
                'tipo':'biblico','fuente':'okru','playback_url':'https://ok.ru/video/10328454335072',
                'imagen_url':'/static/support/popcorn.svg','sinopsis':'Fragmento de 7 minutos de ESTUDIOS 421; no es la serie completa.',
                'duracion':'7 min','genero':'Bíblico','disponible':True,'destacado':False,'descarga':None}).execute()
    from billing.schema import access
    from sqlalchemy import select
    owner = security_store.account(telegram_id=5824989040)
    if not owner: owner = security_store.create_account('Ale',telegram_id=5824989040)
    with security_store.engine.begin() as connection:
        if not connection.execute(select(access).where(access.c.account_id==owner['id'])).first():
            connection.execute(access.insert().values(account_id=owner['id'],expires_at=time.time()+30*86400))
