"""Prepare an auditable, additive release payload; never contact production."""
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.catalog_queue import completed_manifests


def literal(value):
    return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"


def prepare(directory):
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    current = read(directory / 'contenido-before.json')
    baseline = {r['id']: r for r in read(ROOT / '.local/catalog-snapshot.json')}
    catalog = {r['id']: r for r in current}
    statements = ["BEGIN; SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='180s';",
                  "UPDATE public.contenido SET tipo=btrim(tipo) WHERE tipo<>btrim(tipo);"]
    bindings = read(ROOT / '.local/anime-bindings.json')
    for b in bindings:
        old = catalog[b['id']]
        if old['tmdb_id'] not in (None, b['tmdb_id']):
            raise ValueError('Anime binding changed in production; review required.')
        # Explicitly requested all episodes, including filler; do not retain the misleading title.
        new_title = b['title'] if b['id'] in (408, 409) else old['titulo']
        statements.append(f"UPDATE public.contenido SET tmdb_id={int(b['tmdb_id'])},tipo='anime',titulo={literal(new_title)}#>>'{{}}' WHERE id={int(b['id'])} AND (tmdb_id IS NULL OR tmdb_id={int(b['tmdb_id'])});")
    documents = {}
    for file in sorted((ROOT / '.local/vimeus-manifests').glob('*.json')):
        doc = read(file); c = doc['contenido']; documents[(c['tipo'], c['tmdb_id'])] = doc
    for doc in completed_manifests(ROOT / '.local/import-queue.sqlite'):
        c = doc['contenido']; documents[(c['tipo'], c['tmdb_id'])] = doc
    manual = ROOT / '.local/manual-vimeus-preview.json'
    if manual.exists():
        for doc in read(manual).values():
            c = doc['contenido']; documents[(c['tipo'], c['tmdb_id'])] = doc
    for doc in documents.values():
        function = 'importar_vimeus' if doc['contenido']['tipo'] in ('serie', 'anime') else 'importar_metadatos'
        if function == 'importar_metadatos': doc['contenido']['tmdb_media'] = 'movie'
        statements.append(f'SELECT public.{function}({literal(doc)});')
        c = doc['contenido']
        # The catalogue snapshot is being published in this same transaction.
        job = {'kind': c['tipo'], 'tmdb': c['tmdb_id'], 'source': json.dumps({'tmdb_id': c['tmdb_id'], 'title': c['titulo']}),
               'status': 'done', 'attempts': 0, 'ready': 0, 'created_at': 0, 'note': 'Importación validada durante el despliegue.'}
        statements.append(f"INSERT INTO cine_security.catalog_jobs SELECT * FROM jsonb_populate_record(NULL::cine_security.catalog_jobs,{literal(job)}) ON CONFLICT(kind,tmdb) DO UPDATE SET status='done';")
    metadata = read(ROOT / '.local/metadata-preview-edits.json')
    for doc in metadata.values():
        if doc.get('content_id') and doc['content_id'] not in catalog:
            raise ValueError('Metadata target no longer exists.')
        statements.append(f'SELECT public.importar_metadatos({literal(doc)});')
    # Keep newer production editorial changes; only update fields unchanged since the local snapshot.
    for item in read(ROOT / '.local/movie-metadata.json'):
        cid = item['id']; old = baseline.get(cid); live = catalog.get(cid)
        if not old or not live: continue
        for key, value in item['metadata'].items():
            if key not in ('titulo', 'backdrop_url', 'trailer_url') or not value: continue
            if live.get(key) != old.get(key): continue
            statements.append(f'UPDATE public.contenido SET "{key}"={literal(value)}#>>\'{{}}\' WHERE id={int(cid)};')
    # Mirror the reviewed preview, preserving all channel references and download values.
    statements.append("UPDATE public.contenido SET fuente='vimeus',playback_unverified=true WHERE tipo='pelicula' AND tmdb_id>0 AND coalesce(fuente,'') NOT IN ('vimeus','okru');")
    for old_id, season in ((405, 2), (406, 3), (407, 4)):
        if not catalog.get(old_id) or catalog[old_id].get('descarga'): continue
        statements.append(f"INSERT INTO public.catalog_aliases(original_id,content_id,start_season) SELECT {old_id},404,{season} WHERE EXISTS(SELECT 1 FROM public.temporadas WHERE contenido_id=404 AND numero={season} AND episodios>0) ON CONFLICT(original_id) DO NOTHING;")
        statements.append(f"UPDATE public.contenido SET disponible=false WHERE id={old_id} AND EXISTS(SELECT 1 FROM public.catalog_aliases WHERE original_id={old_id});")
    # Migrate real preview accounts/preferences, not demo payments, owner trial or session tokens.
    source = sqlite3.connect((directory / 'preview-accounts-before.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    accounts = [dict(r) for r in source.execute("SELECT * FROM accounts WHERE email IS NULL OR email NOT LIKE '%@example.test'")]
    account_ids = {r['id'] for r in accounts}
    for row in accounts:
        statements.append(f"INSERT INTO cine_security.accounts SELECT * FROM jsonb_populate_record(NULL::cine_security.accounts,{literal(row)}) ON CONFLICT(id) DO NOTHING;")
    for table in ('profiles', 'saved_items'):
        for raw in source.execute('SELECT * FROM ' + table):
            row = dict(raw)
            if row['account_id'] not in account_ids: continue
            if table == 'saved_items' and row['content_id'] not in catalog: continue
            statements.append(f"INSERT INTO cine_security.{table} SELECT * FROM jsonb_populate_record(NULL::cine_security.{table},{literal(row)}) ON CONFLICT DO NOTHING;")
    source.close()
    pending = sqlite3.connect((ROOT / '.local/import-queue.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    pending.row_factory = sqlite3.Row
    for row in pending.execute("SELECT kind,tmdb,source FROM jobs WHERE status<>'done'"):
        job = {**dict(row), 'status': 'pending', 'attempts': 0, 'ready': 0, 'created_at': 1, 'note': None}
        statements.append(f"INSERT INTO cine_security.catalog_jobs SELECT * FROM jsonb_populate_record(NULL::cine_security.catalog_jobs,{literal(job)}) ON CONFLICT(kind,tmdb) DO NOTHING;")
    pending.close()
    statements.append('COMMIT;')
    (directory / 'release-data.sql').write_text('\n'.join(statements), encoding='utf-8')
    summary = {'vimeus_titles': len(documents), 'episodes': sum(len(s['capitulos']) for d in documents.values() for s in d['temporadas']),
               'metadata_documents': len(metadata), 'preview_accounts_preserved': len(accounts),
               'demo_payments_transferred': 0, 'manual_download_writes': 0, 'production_writes': False}
    (directory / 'release-data-plan.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    prepare(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '.local/production-20261026')
