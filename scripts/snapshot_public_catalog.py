"""Read-only public catalogue snapshot. Never reads users, payments or credentials."""
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
base = 'https://cineapp-bot.onrender.com'
rows = {}
offset = 0
session = requests.Session()
for page in range(100):
    response = session.post(base+'/api/contenido', json={'tipo':'todo','limit':50,'offset':offset},timeout=30)
    response.raise_for_status()
    payload = response.json()
    batch = payload['data']
    if not batch: break
    for row in batch: rows[row['id']] = row
    offset += len(batch)
    if offset >= payload['total']: break
else:
    raise RuntimeError('Pagination limit exceeded; snapshot not replaced.')
target = ROOT/'.local/catalog-snapshot.json'
target.write_text(json.dumps(list(rows.values()),ensure_ascii=False),encoding='utf-8')
print(f'Saved {len(rows)} public catalogue entries locally. No production writes.')
