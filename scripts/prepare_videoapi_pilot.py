"""Read-only availability probe. Writes only a local allowlist, never imports titles."""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_support import LocalDatabase
from security_store import SecurityStore
from billing import schema  # register local membership tables
from scripts.seed_telegram_preview import seed_preview
from providers.videoapi import KINDS


def fingerprint(db):
    return hashlib.sha256(json.dumps(db.rows, sort_keys=True, default=str).encode()).hexdigest()


def main():
    db = LocalDatabase()
    seed_preview(db, SecurityStore('sqlite:///:memory:', local=True))
    before = fingerprint(db)
    entries, checks = {}, []
    preferred = [22, 58, 550, 285, 94997, 19614, 1399, 46260, 31910, 12971]
    session = requests.Session()
    for kind, quota in [('pelicula', 4), ('serie', 3), ('anime', 3)]:
        rows = [r for r in db.rows['contenido'] if r.get('tipo') == kind and r.get('fuente') == 'vimeus' and r.get('tmdb_id')]
        rows.sort(key=lambda r: (preferred.index(int(r['tmdb_id'])) if int(r['tmdb_id']) in preferred else 100, r['id']))
        accepted = 0
        for row in rows[:12]:
            seasons = {s['id']: s['numero'] for s in db.rows['temporadas'] if s['contenido_id'] == row['id'] and s['numero'] > 0}
            pairs = sorted({(seasons[e['temporada_id']], e['numero']) for e in db.rows['episodios'] if e.get('disponible') and e['temporada_id'] in seasons})[:2] if kind != 'pelicula' else [None]
            if not pairs:
                continue
            verified = []
            for pair in pairs:
                url = f"https://videoapi.la/api/v1/public/exists/{KINDS[kind]}/{int(row['tmdb_id'])}"
                if pair:
                    url += f'/{pair[0]}/{pair[1]}'
                start = time.monotonic()
                try:
                    response = session.get(url, timeout=(5, 15), allow_redirects=False)
                    available = response.status_code == 200 and response.json().get('exists') is True
                    checks.append({'title': row['titulo'], 'url': url, 'status': response.status_code, 'exists': available, 'seconds': round(time.monotonic()-start, 2)})
                except (requests.RequestException, ValueError):
                    available = False
                    checks.append({'title': row['titulo'], 'url': url, 'exists': False, 'error': 'Unavailable'})
                if available:
                    verified.append(list(pair) if pair else None)
                time.sleep(.4)
            if len(verified) != len(pairs):
                continue
            entries[str(row['id'])] = {'tmdb_id': row['tmdb_id'], 'tipo': kind, 'titulo': row['titulo'], 'episodes': [v for v in verified if v]}
            accepted += 1
            if accepted == quota:
                break
    assert before == fingerprint(db), 'Availability checks must never modify catalog or downloads'
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'entries': entries, 'checks': checks,
              'catalog_unchanged': True, 'titles_before': len(db.rows['contenido']), 'titles_after': len(db.rows['contenido'])}
    target = ROOT/'.local/videoapi-pilot.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
