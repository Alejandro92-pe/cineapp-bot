"""Refresh only ratings in completed LOCAL batch snapshots. Never writes Supabase."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from providers.tmdb import TMDBClient, tmdb_rating
from services.catalog_queue import CatalogQueue, PacedTransport, worker_lock


def main(ids):
    folder = ROOT / '.local'
    secret = json.loads((folder / 'telegram-preview.json').read_text(encoding='utf-8'))
    with worker_lock(folder / 'import-queue.lock'):
        queue = CatalogQueue(folder / 'import-queue.sqlite')
        transport = PacedTransport(queue, 1.2, 90)
        client = TMDBClient(secret['TMDB_API_KEY'], transport)
        changes, before = [], []
        for tmdb in ids:
            rows = queue.db.execute("SELECT kind, manifest FROM jobs WHERE tmdb=? AND status='done'", (tmdb,)).fetchall()
            if len(rows) != 1:
                raise ValueError('El título no pertenece a un único lote completado.')
            kind, raw = rows[0]
            document = json.loads(raw)
            metadata = client.get(f"/{'movie' if kind == 'pelicula' else 'tv'}/{tmdb}")
            rating = tmdb_rating(metadata)
            if metadata.get('id') != tmdb or rating is None:
                raise ValueError('TMDB no devolvió una puntuación válida para ese título.')
            original = copy.deepcopy(document)
            document['contenido']['rating'] = rating
            before.append({'kind': kind, 'tmdb': tmdb, 'manifest': original})
            changes.append((kind, tmdb, document))
        backup = folder / 'phase15-ratings-before.json'
        if not backup.exists():
            backup.write_text(json.dumps(before, ensure_ascii=False), encoding='utf-8')
        with queue.db:
            for kind, tmdb, doc in changes:
                queue.db.execute("UPDATE jobs SET manifest=? WHERE kind=? AND tmdb=? AND status='done'",
                    (json.dumps(doc, ensure_ascii=False), kind, tmdb))
        report = {'requests': transport.requests, 'titles': [
            {'tmdb_id': tmdb, 'title': doc['contenido']['titulo'], 'rating': doc['contenido']['rating'],
             'episodes': sum(len(s['capitulos']) for s in doc['temporadas'])} for _, tmdb, doc in changes]}
        (folder / 'phase15-ratings.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ids', type=int, nargs='+')
    args = parser.parse_args()
    try:
        main(list(dict.fromkeys(args.ids)))
    except Exception:
        print('No se completó la actualización de puntajes. Revisa la conexión; no se ha contactado Supabase.', file=sys.stderr)
        sys.exit(1)
