"""Small live-provider rehearsal. Reads TMDB credentials, writes ONLY .local.

Uses the production queue/adapter and a copied catalog. Batch scheduling is
accelerated for this rehearsal; the real 1.5-second HTTP pacing is preserved.
No Supabase client, Telegram bot, Render or production write is instantiated.
"""
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from sqlalchemy import update

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from security_store import SecurityStore
from local_support import LocalDatabase
from scripts.seed_telegram_preview import seed_preview
from services.videoapi_jobs import VideoAPIQueue, jobs
from services.catalog_jobs import CachedTransport
from providers.videoapi_catalog import VideoAPICatalog
from providers.tmdb import TMDBClient
from services.local_videoapi import apply_local


def downloads(db):
    fields=('descarga','enlace','enlace_canal','provider_download_url','playback_url')
    return {(table,row['id']):{k:row.get(k) for k in fields if row.get(k)}
            for table in ('contenido','temporadas','episodios') for row in db.rows.get(table,[])
            if any(row.get(k) for k in fields)}


def main():
    out=ROOT/'.local/videoapi-import';out.mkdir(exist_ok=True)
    # Explicitly discard all configuration except the TMDB read-only credential.
    saved=json.loads((ROOT/'.local/production-20261026/render-before.json').read_text(encoding='utf-8'))
    key=next((r['value'] for r in saved if r['key']=='TMDB_API_KEY'),'')
    if not key:raise SystemExit('Falta la clave TMDB local; no se consultó producción.')
    run=out/'runs'/datetime.now().strftime('%Y%m%d-%H%M%S-%f');run.mkdir(parents=True)
    store=SecurityStore('sqlite:///'+(run/'queue.sqlite').as_posix(),local=True)
    queue=VideoAPIQueue(store);db=LocalDatabase();seed_preview(db,store)
    before=downloads(db);before_ids={r['id'] for r in db.rows['contenido']}
    documents=[];batches=[]
    for resource in ('movies','series','animes'):
        # One real title per category, with real pagination validation.
        transport=CachedTransport(queue,seconds=1.5,max_seconds=18)
        if not queue.get_setting('finished:'+resource):
            queue.discover(VideoAPICatalog(transport,page_size=1),resource)
            queue.set_setting('finished:'+resource,time.time())
    def publish(doc):
        result=apply_local(db,doc)
        # Repeat the same real manifest and compare catalog state byte-for-byte.
        first=json.dumps(db.rows,sort_keys=True,default=str)
        again=apply_local(db,doc)
        assert result['contenido_id']==again['contenido_id']
        assert first==json.dumps(db.rows,sort_keys=True,default=str)
        documents.append(doc)
        return result
    for index in range(15):
        # Local rehearsal only: fast-forward the scheduling gate, NOT HTTP pacing.
        queue.set_setting('batch_after',0)
        with store.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.status=='pending').values(ready=0))
        transport=CachedTransport(queue,seconds=1.5,max_seconds=18)
        started=time.monotonic()
        result=queue.run(VideoAPICatalog(transport),TMDBClient(key,transport).get,publish,discover=False)
        batches.append({**result,'seconds':round(time.monotonic()-started,2),'http_requests':transport.requests})
        print(json.dumps(batches[-1]),flush=True)
        if queue.summary().get('done',0)==3 or queue.summary().get('failed',0):break
        time.sleep(1)
    after=downloads(db)
    assert all(after.get(k)==v for k,v in before.items()),'Cambió un enlace existente'
    assert before_ids.issubset({r['id'] for r in db.rows['contenido']})
    (out/'manifests.json').write_text(json.dumps(documents,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'production_writes':0,'queue':queue.summary(),'downloads_preserved':len(before),
        'reimport_idempotent':True,'http_pause_seconds':1.5,'batch_budget_seconds':18,
        'local_schedule_accelerated':True,'batches':batches,
        'titles':[{'title':d['contenido']['titulo'],'kind':d['contenido']['tipo'],'tmdb_id':d['contenido']['tmdb_id'],
            'seasons':len(d['temporadas']),'episodes':sum(len(s['capitulos']) for s in d['temporadas'])} for d in documents]}
    (out/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'complete':summary['queue'].get('done')==3,'titles':summary['titles']},ensure_ascii=True))


if __name__=='__main__':main()
