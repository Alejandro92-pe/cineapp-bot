"""Offline HTTP contention rehearsal, not a Render benchmark.

Real Flask routes, copied public catalog, isolated SQLite accounts/queue. External
responses are fixtures with 100ms latency; real 1.5s pacing and 18s budgets remain.
ABBA compares idle/import/import/idle with four HTTP clients in the same process.
The importer runs continuously in active windows (a stress test, NOT a cron).
"""
import os, sys, json, time, threading, statistics, math, copy, socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'.local/import-priority';OUT.mkdir(exist_ok=True)
RUN=OUT/time.strftime('bench-%Y%m%d-%H%M%S');RUN.mkdir()
with socket.socket() as reserved:
 reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
origin=f'http://127.0.0.1:{port}'
os.environ.update(APP_MODE='local',APP_ORIGIN=origin,
 SECURITY_DATABASE_URL='sqlite:///'+(RUN/'isolated.sqlite').as_posix(),
 BOT_TOKEN='123456:OFFLINE',SUPABASE_URL='',SUPABASE_KEY='',SUPABASE_SERVICE_KEY='',
 VIMEUS_API_KEY='',VIMEUS_VIEW_KEY='',TMDB_API_KEY='',VIDEOAPI_ENABLED='false',
 TELEGRAM_PREVIEW='false',CRON_SECRET='offline-cron-'*4,TELEGRAM_WEBHOOK_SECRET='offline-hook-'*4,
 BMC_WEBHOOK_SECRET='offline-payment-'*4,BMC_MONTHLY_READY='false')
from local_support import block_external_network
block_external_network()
from security import password_hash
os.environ['ADMIN_PASSWORD_HASH']=password_hash('Offline-only-benchmark-2026!')
import main
from security_store import accounts, sessions
from services.videoapi_jobs import VideoAPIQueue
from services.catalog_jobs import CachedTransport
from services.local_videoapi import apply_local
from sqlalchemy import select
from werkzeug.serving import make_server, WSGIRequestHandler
import requests

backup=json.loads((ROOT/'.local/videoapi-production/backup-private.json').read_text())
db=main.supabase_service
for table in ('contenido','temporadas','episodios'):
 db.rows[table]=copy.deepcopy(backup['public.'+table])
del backup
owner=main.security_store.create_account('Owner fixture',telegram_id=5824989040)
token,csrf=main.security_store.new_session(owner['id'],604800,False)
def account_snapshot():
 with main.security_store.engine.connect() as c:
  return [dict(r) for r in c.execute(select(accounts)).mappings()]
def downloads():
 return {(table,r['id']):tuple(r.get(k) for k in ('descarga','provider_download_url','playback_url','enlace'))
  for table in ('contenido','temporadas','episodios') for r in db.rows[table]}
before_accounts=account_snapshot();before_downloads=downloads()
documents=json.loads((ROOT/'.local/videoapi-import/manifests.json').read_text())
docs={d['contenido']['tmdb_id']:d for d in documents}
assert len(docs)==3
queue=VideoAPIQueue(main.security_store)
class FixtureProvider:
 def __init__(self,t):self.t=t
 def page(self,resource,page):
  kind={'movies':'pelicula','series':'serie','animes':'anime'}[resource]
  return [{'tmdb_id':i,'title':d['contenido']['titulo']} for i,d in docs.items() if d['contenido']['tipo']==kind],{'has_next':False}
 def exists(self,kind,tmdb,season=None,episode=None):
  self.t.get(f'https://fixture.invalid/exists/{kind}/{tmdb}/{season}/{episode}')
  return True
def metadata(path,params=None):
 parts=path.strip('/').split('/');doc=docs[int(parts[1])]
 if parts[-1]=='videos':return {'results':[]}
 if 'season' in parts:
  s=next(s for s in doc['temporadas'] if s['numero']==int(parts[-1]))
  return {'season_number':s['numero'],'episodes':[{'season_number':s['numero'],'episode_number':e['numero'],'name':e['titulo']} for e in s['capitulos']]}
 return {'id':int(parts[1]),'title':doc['contenido']['titulo'],'name':doc['contenido']['titulo'],
  'seasons':[{'season_number':s['numero'],'episode_count':len(s['capitulos'])} for s in doc['temporadas']]}
def response(url,**kwargs):
 time.sleep(.1)
 payload=metadata(url.split('/tmdb',1)[1]) if '/tmdb/' in url else {'ok':True}
 return SimpleNamespace(status_code=200,headers={},json=lambda:payload)
for resource in ('movies','series','animes'):
 queue.discover(FixtureProvider(None),resource)

class Quiet(WSGIRequestHandler):
 def log(self,*a,**kw):pass
server=make_server('127.0.0.1',port,main.app,threaded=True,request_handler=Quiet)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=origin
season=next(s['id'] for s in db.rows['temporadas'] if s['contenido_id']==408 and s['numero']==1)
paths=[('home','GET','/',None),('catalog','POST','/api/contenido',{'limit':20}),
 ('detail','GET','/api/temporadas/408',None),('episodes','GET',f'/api/episodios/408/{season}?page_size=12',None),
 ('account','GET','/api/auth/me',None)]
samples=[];batches=[];errors=[]
def viewer(until,phase):
 s=requests.Session();s.cookies.set('cine_session',token)
 while time.monotonic()<until:
  for name,method,path,body in paths:
   start=time.perf_counter()
   r=s.request(method,base+path,json=body,headers={'Origin':origin},timeout=10)
   samples.append({'phase':phase,'endpoint':name,'ms':(time.perf_counter()-start)*1000,'status':r.status_code})
   if r.status_code!=200:errors.append({'path':path,'status':r.status_code})
   if name=='account' and r.status_code==200:assert r.json()['authenticated']
  time.sleep(1)
 s.close()
def importer(until):
 while time.monotonic()<until:
  # Accelerate only local scheduling; never change outbound pacing or budgets.
  queue.set_setting('batch_after',0)
  from services.videoapi_jobs import jobs
  with queue.engine.begin() as c:
   c.execute(jobs.update().where(jobs.c.status=='pending').values(ready=0))
  t=CachedTransport(queue,seconds=1.5,max_seconds=18,session=SimpleNamespace(get=response))
  start=time.monotonic()
  result=queue.run(FixtureProvider(t),lambda path,params=None:t.get('https://fixture.invalid/tmdb'+path).json(),
                   lambda doc:apply_local(db,doc),discover=False)
  batches.append({**result,'seconds':round(time.monotonic()-start,3),'requests':t.requests})
  if queue.summary().get('done')==3:break
  time.sleep(.15)
try:
 # Warm the same endpoints before collecting latency.
 viewer(time.monotonic()+1,'warmup');assert not errors,errors[:5]
 samples.clear();errors.clear()
 for phase in ('idle_1','active_1','active_2','idle_2'):
  # Re-arm only local fixture jobs for equal active windows, retaining real cache.
  if phase.startswith('active'):
   from services.videoapi_jobs import jobs
   with queue.engine.begin() as c:
    for row in c.execute(select(jobs)).mappings().all():
     source=json.loads(row['source']);source.pop('progress',None)
     c.execute(jobs.update().where(jobs.c.kind==row['kind'],jobs.c.tmdb==row['tmdb']).values(
         status='pending',ready=0,source=json.dumps(source)))
   from services.catalog_jobs import cache
   with queue.engine.begin() as c:c.execute(cache.delete())
  until=time.monotonic()+18
  with ThreadPoolExecutor(max_workers=5) as pool:
   workers=[pool.submit(viewer,until,phase) for _ in range(4)]
   if phase.startswith('active'):workers.append(pool.submit(importer,until))
   for w in workers:w.result()
  print(json.dumps({'phase':phase,'samples':sum(x['phase']==phase for x in samples),'errors':len(errors)}),flush=True)
finally:server.shutdown()
assert not errors,errors
assert account_snapshot()==before_accounts
after_downloads=downloads()
assert all(after_downloads.get(k)==v for k,v in before_downloads.items())
def stats(values):
 values=sorted(values)
 return {'n':len(values),'median_ms':round(statistics.median(values),2),'p95_ms':round(values[math.ceil(len(values)*.95)-1],2),'max_ms':round(max(values),2)}
metrics={group:{name:stats([r['ms'] for r in samples if r['phase'].startswith(group) and r['endpoint']==name]) for name,_,_,_ in paths} for group in ('idle','active')}
result={'environment':'Windows local Flask threaded; SQLite; catalog in memory; four concurrent clients',
 'not_render_measurement':True,'external_io':'blocked; fixture responses with 100ms delay',
 'http_pacing_seconds':1.5,'batch_budget_seconds':18,'local_continuous_import_stress':True,
 'counts':{k:len(db.rows[k]) for k in ('contenido','temporadas','episodios')},'metrics':metrics,
 'errors':errors,'accounts_preserved':True,'existing_download_rows_preserved':len(before_downloads),'batches':batches}
(OUT/'benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(RUN/'samples.json').write_text(json.dumps(samples),encoding='utf-8')
print(json.dumps(result),flush=True)
