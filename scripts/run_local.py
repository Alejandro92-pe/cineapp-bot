"""Run only on loopback with synthetic data and no outbound connections."""
import os
import argparse
import json
import re
import secrets
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
LOCAL = ROOT / ".local"
LOCAL.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--public-origin')
parser.add_argument('--videoapi-pilot', action='store_true', help='Local catalog copy with checked VideoAPI samples; no production writes')
args = parser.parse_args()
preview = bool(args.public_origin)
if preview:
    from services.preview import validate_preview_origin
    validate_preview_origin(args.public_origin)
# Deliberately override inherited production settings. Never load .env.
os.environ.update(APP_MODE="local", APP_ORIGIN="http://127.0.0.1:5010",
    SECURITY_DATABASE_URL="sqlite:///"+(LOCAL/"accounts.sqlite").as_posix(),
    BOT_TOKEN="123456:LOCAL_ONLY_NOT_A_REAL_TOKEN", SUPABASE_URL="", SUPABASE_KEY="", SUPABASE_SERVICE_KEY="",
    VIMEUS_VIEW_KEY="", VIMEUS_API_KEY="", TMDB_API_KEY="", PAYPAL_CLIENT_ID="", PAYPAL_CLIENT_SECRET="",
    GMAIL_USER="", GMAIL_PASSWORD="", CRON_SECRET=secrets.token_urlsafe(32),
    TELEGRAM_WEBHOOK_SECRET=secrets.token_urlsafe(32), BMC_WEBHOOK_SECRET=secrets.token_urlsafe(32),
    BMC_MONTHLY_PRODUCT_ID="517243", BMC_MONTHLY_READY="false")
os.environ['TELEGRAM_PREVIEW'] = 'true' if preview else 'false'
os.environ['VIDEOAPI_ENABLED'] = 'true' if args.videoapi_pilot else 'false'
if preview:
    os.environ.update(APP_ORIGIN=args.public_origin,
        SECURITY_DATABASE_URL='sqlite:///'+(LOCAL/'telegram-preview.sqlite').as_posix())
    secret_file = LOCAL/'telegram-preview.json'
    if secret_file.exists():
        values = json.loads(secret_file.read_text(encoding='utf-8'))
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',values.get('BOT_TOKEN','')):
            raise SystemExit('BOT_TOKEN local inválido; revisa el archivo sin publicar su contenido.')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,64}',values.get('BOT_USERNAME','')):
            raise SystemExit('BOT_USERNAME local inválido.')
        for key in ('BOT_TOKEN', 'BOT_USERNAME', 'VIMEUS_VIEW_KEY'):
            if values.get(key): os.environ[key] = values[key]
elif args.videoapi_pilot:
    secret_file = LOCAL/'telegram-preview.json'
    if secret_file.exists():
        os.environ['VIMEUS_VIEW_KEY'] = json.loads(secret_file.read_text(encoding='utf-8')).get('VIMEUS_VIEW_KEY', '')
from local_support import block_external_network
block_external_network()
from security import password_hash
credentials = LOCAL / "access.txt"
if not credentials.exists():
    credentials.write_text("Admin local: 5824989040\nContraseña local: "+secrets.token_urlsafe(18)+"\n", encoding="utf-8")
password = credentials.read_text(encoding="utf-8").split("Contraseña local: ")[1].strip()
os.environ["ADMIN_PASSWORD_HASH"] = password_hash(password)
from main import app
from main import security_store
demo_credentials = LOCAL / "payment-demo.txt"
if not demo_credentials.exists():
    demo_credentials.write_text("Correo local: pagos@example.test\nContraseña local: "+secrets.token_urlsafe(18)+"\n", encoding="utf-8")
demo_password = demo_credentials.read_text(encoding="utf-8").split("Contraseña local: ")[1].strip()
if not security_store.account(email="pagos@example.test"):
    security_store.create_account("Cuenta de pagos local", email="pagos@example.test", password_hash=password_hash(demo_password))
from main import vimeus_provider, supabase_service
from services.vimeus_import import import_title, ImportRepository
for demo_id, kind in ((900101, "serie"), (900202, "anime")):
    imported = import_title(vimeus_provider, ImportRepository(supabase_service), demo_id, kind)
    supabase_service.table("contenido").update({"imagen_url": "/static/placeholder.svg",
        "sinopsis": "Contenido ficticio para revisar temporadas, capítulos y descargas. La vista local no reproduce vídeos externos.",
        "descarga": "https://www.mediafire.com/file/local-test/example/file"}).eq("id", imported["contenido_id"]).execute()
from scripts.seed_local_catalog import seed_catalog
seed_catalog(supabase_service)
if preview or args.videoapi_pilot:
    from scripts.seed_telegram_preview import seed_preview
    seed_preview(supabase_service, security_store)
if args.videoapi_pilot:
    app.config['VIDEOAPI_PILOT'] = json.loads((LOCAL/'videoapi-pilot.json').read_text(encoding='utf-8'))['entries']
from services.manual_vimeus import restore as restore_manual_vimeus
restore_manual_vimeus(supabase_service,LOCAL/('manual-vimeus-preview.json' if preview or args.videoapi_pilot else 'manual-vimeus-demo.json'))
app.config['ALLOW_PREVIEW_METADATA_FETCH']=preview
from services.metadata_import import restore as restore_metadata
restore_metadata(supabase_service,LOCAL/('metadata-preview-edits.json' if preview or args.videoapi_pilot else 'metadata-demo-edits.json'))
from services.okru_editor import restore as restore_okru
restore_okru(supabase_service,LOCAL/('okru-preview-edits.json' if preview or args.videoapi_pilot else 'okru-demo-edits.json'))
# Manual downloads restore last, including newly created biblical episodes.
if preview or args.videoapi_pilot:
    from services.preview_downloads import restore as restore_downloads
    restore_downloads(supabase_service,LOCAL/'episode-downloads.json')
print('Vista local: '+os.environ['APP_ORIGIN']+'/cuenta', flush=True)
print("Credencial de prueba en .local/access.txt. No es tu contraseña de producción.", flush=True)
app.run(host="127.0.0.1", port=5011 if preview else 5010, debug=False, use_reloader=False)
