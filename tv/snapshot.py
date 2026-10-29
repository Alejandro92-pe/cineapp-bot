"""Build an isolated TV catalog from local copies and optional public GETs.

Never copies accounts, cookies, payment data, download or channel URLs.
"""
import argparse
import json
import time
from pathlib import Path
import requests

TITLE_FIELDS = {'id','titulo','tipo','año','genero','sinopsis','imagen_url',
                'backdrop_url','rating','tmdb_id','fuente','playback_url',
                'trailer_url','disponible','videoapi_enabled'}
SEASON_FIELDS = {'numero','nombre','poster_url','descripcion'}
EP_FIELDS = {'numero','titulo','sinopsis','imagen_url','duracion','playback_url','disponible'}


def prepare(root, refresh=False):
    backup_path = root/'videoapi-production/backup-private.json'
    backup = json.loads(backup_path.read_text(encoding='utf-8-sig')) if backup_path.exists() else {}
    old = {x['id']: x for x in backup.get('public.contenido', [])}
    current = json.loads((root/'visual-refresh/catalog-all.json').read_text(encoding='utf-8-sig'))
    titles = [{k:v for k,v in {**old.get(x['id'], {}), **x}.items() if k in TITLE_FIELDS} for x in current]
    artwork = root/'visual-refresh/backfill.json'
    if artwork.exists():
        by_id = {x['id']:x for x in titles}
        for row in json.loads(artwork.read_text(encoding='utf-8-sig')).values():
            if row['id'] in by_id and row.get('backdrop_url'):
                by_id[row['id']]['backdrop_url'] = row['backdrop_url']
    valid = {x['id'] for x in titles}
    seasons, episodes, old_seasons = {}, {}, {}
    for s in backup.get('public.temporadas', []):
        if s['contenido_id'] not in valid: continue
        key = (s['contenido_id'], s['numero'])
        old_seasons[s['id']] = key
        seasons[key] = {k:v for k,v in s.items() if k in SEASON_FIELDS}
    for ep in backup.get('public.episodios', []):
        if ep['temporada_id'] in old_seasons:
            key = (*old_seasons[ep['temporada_id']], ep['numero'])
            episodes[key] = {k:v for k,v in ep.items() if k in EP_FIELDS}
    # Do not retain unrelated private sections of the backup.
    del backup, old
    paths = list((root/'vimeus-manifests').glob('*.json')) + list((root/'tmdb-imports').glob('*.json'))
    for path in sorted(paths):
        m = json.loads(path.read_text(encoding='utf-8-sig'))
        meta = m.get('contenido', {})
        match = next((x for x in titles if meta.get('tmdb_id') and str(x.get('tmdb_id')) == str(meta['tmdb_id']) and x['tipo'] == meta.get('tipo')), None)
        if not match: continue
        for s in m.get('temporadas', []):
            key = (match['id'], s['numero'])
            seasons.setdefault(key, {k:v for k,v in s.items() if k in SEASON_FIELDS})
            for ep in s.get('capitulos', []):
                episodes.setdefault((*key, ep['numero']), {**{k:v for k,v in ep.items() if k in EP_FIELDS}, 'disponible': ep.get('disponible', True)})
    failures, fetched = [], 0
    with_episodes = {key[0] for key, ep in episodes.items() if ep.get('disponible', True)}
    if refresh:
        session = requests.Session()
        def public(path):
            nonlocal fetched
            time.sleep(.5)
            r = session.get('https://app.quehay.live'+path, timeout=25)
            r.raise_for_status(); fetched += 1
            return r.json()
        for item in titles:
            if item['tipo'] not in ('serie','anime','biblico') or item['id'] in with_episodes: continue
            cid = item['id']
            try:
                remote = public(f'/api/temporadas/{cid}')
                for s in remote.get('temporadas', []):
                    key = (cid, s['numero'])
                    staged = []
                    for page in range(1, 101):
                        result = public(f'/api/episodios/{cid}/{s["id"]}?page_size=50&page={page}')
                        staged.extend(result.get('episodios', []))
                        if not result.get('has_next'): break
                    else: raise ValueError('Episode pagination exceeded bound')
                    seasons[key] = {k:v for k,v in s.items() if k in SEASON_FIELDS}
                    for ep in staged:
                        ek = (*key, ep['numero'])
                        episodes[ek] = {**episodes.get(ek, {}), **{k:v for k,v in ep.items() if k in EP_FIELDS}, 'disponible': True}
            except (requests.RequestException, ValueError, KeyError) as exc:
                failures.append({'id':cid, 'error':type(exc).__name__})
    season_rows, episode_rows = [], []
    for key, s in sorted(seasons.items()):
        sid = len(season_rows)+1
        eps = [(ek, ep) for ek,ep in episodes.items() if ek[:2] == key]
        season_rows.append({**s,'id':sid,'contenido_id':key[0], 'episodios':sum(ep.get('disponible',True) for _,ep in eps)})
        for _, ep in sorted(eps):
            episode_rows.append({**ep,'id':len(episode_rows)+1,'temporada_id':sid})
    loaded = {s['contenido_id'] for s in season_rows if s['episodios']}
    missing = [{'id':x['id'],'titulo':x['titulo']} for x in titles if x['tipo'] in ('serie','anime') and x['id'] not in loaded]
    report = {'titles':len(titles),'seasons':len(season_rows),'episodes':len(episode_rows),
              'episodic_titles':len(loaded),'missing':missing,'public_gets':fetched,'errors':failures}
    return {'contenido':titles,'temporadas':season_rows,'episodios':episode_rows}, report


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot-root',type=Path,required=True);p.add_argument('--refresh-missing',action='store_true')
    args=p.parse_args();data,report=prepare(args.snapshot_root,args.refresh_missing)
    out=Path(__file__).resolve().parents[1]/'.local/tv';out.mkdir(parents=True,exist_ok=True)
    (out/'catalog.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    (out/'catalog-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
