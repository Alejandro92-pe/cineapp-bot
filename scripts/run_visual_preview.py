"""Loopback-only visual preview, isolated accounts and offline catalogue copy."""
import os
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
OUT=ROOT/'.local/visual-refresh'
os.environ.update(APP_MODE='local',APP_ORIGIN='http://127.0.0.1:5014',APP_ORIGIN_ALIASES='',
 SECURITY_DATABASE_URL='sqlite:///'+(OUT/'preview.sqlite').as_posix(),BOT_TOKEN='123456:LOCAL_ONLY',
 SUPABASE_URL='',SUPABASE_KEY='',SUPABASE_SERVICE_KEY='',TMDB_API_KEY='',VIMEUS_API_KEY='',VIMEUS_VIEW_KEY='',
 PAYPAL_CLIENT_ID='',PAYPAL_CLIENT_SECRET='',GMAIL_USER='',GMAIL_PASSWORD='',TELEGRAM_PREVIEW='false',
 VIDEOAPI_ENABLED='false',CATALOG_IMPORT_ENABLED='false',ARTWORK_REFRESH_ENABLED='false',BMC_MONTHLY_READY='false')
from local_support import block_external_network
block_external_network()
from main import app,supabase_service,catalog_job_store,security_store
from scripts.seed_telegram_preview import seed_preview
seed_preview(supabase_service,security_store)
from services.artwork import ArtworkMaintenance,SNAPSHOT
from services.hero import PERIOD,LIMA_OFFSET
import time
rows=supabase_service.rows['contenido']
fresh=json.loads((OUT/'catalog-all.json').read_text(encoding='utf-8'))
new=json.loads((OUT/'catalog-2026.json').read_text(encoding='utf-8'))['data']
heroes=json.loads((OUT/'heroes.json').read_text(encoding='utf-8'))
merged={r['id']:r for r in rows}
for r in fresh+new+heroes:merged[r['id']]={**merged.get(r['id'],{}),**r}
if (OUT/'backfill.json').exists():
    for r in json.loads((OUT/'backfill.json').read_text(encoding='utf-8')).values():
        if r['backdrop_url'] and r['id'] in merged:merged[r['id']]['backdrop_url']=r['backdrop_url']
supabase_service.rows['contenido']=list(merged.values())
service=ArtworkMaintenance(catalog_job_store,supabase_service)
service.save(SNAPSHOT,json.loads((OUT/'selection.json').read_text(encoding='utf-8')))
service.save(f'hero:{int((time.time()-LIMA_OFFSET)//PERIOD)}',[r['id'] for r in heroes])
app.run(host='127.0.0.1',port=5014,debug=False,use_reloader=False)
