"""Paced, resumable TMDB reads. Produces local image-only changes, no Supabase client."""
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from providers.tmdb import TMDBClient
from services.artwork import metadata_for,needs_backdrop,image


def prepare(limit,retry=False):
    folder=ROOT/'.local/visual-refresh'
    rows=json.loads((folder/'catalog-all.json').read_text(encoding='utf-8'))
    path=folder/'backfill.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if retry:saved={k:v for k,v in saved.items() if v.get('backdrop_url')}
    key=json.loads((ROOT/'.local/telegram-preview.json').read_text(encoding='utf-8'))['TMDB_API_KEY']
    client=TMDBClient(key,timeout=(3,6));done=0
    for row in rows:
        if not needs_backdrop(row) or str(row['id']) in saved:continue
        try:meta=metadata_for(row,client)
        except Exception:
            print(json.dumps({'paused_at':row['id'],'reason':'TMDB unavailable; no production changes'}),flush=True);break
        bg=image(meta.get('backdrop_path'),1280)
        saved[str(row['id'])]={'id':row['id'],'titulo':row['titulo'],'tipo':row['tipo'],'tmdb_id':row.get('tmdb_id'),
            'previous_backdrop':row.get('backdrop_url'),'backdrop_url':bg,'matched_tmdb':meta.get('id')}
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
        done+=1
        if done%25==0:print(json.dumps({'reviewed_total':len(saved),'with_backdrop':sum(bool(r['backdrop_url']) for r in saved.values())}),flush=True)
        if done>=limit:break
        time.sleep(.4)
    report={'reviewed_total':len(saved),'with_backdrop':sum(bool(r['backdrop_url']) for r in saved.values()),'pending':sum(needs_backdrop(r) and str(r['id']) not in saved for r in rows),'production_writes':0}
    (folder/'backfill-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=50);p.add_argument('--retry-unmatched',action='store_true');a=p.parse_args();prepare(max(1,min(a.limit,1000)),a.retry_unmatched)
