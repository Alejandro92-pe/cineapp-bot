"""Build a standalone static landing; never changes a server or DNS."""
import argparse
import shutil
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--app-origin', choices=['https://cineapp-bot.onrender.com', 'https://app.quehay.live','http://127.0.0.1:5014'], default='https://app.quehay.live')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
shutil.copytree(ROOT/'assets',args.out/'assets',dirs_exist_ok=True)
# SiteGround/browser caches public assets for a year. A changed file must get a
# new URL, including the bundled background when the selection IDs stay equal.
def version_asset(match):
    source=ROOT/'assets'/match[1]
    if not source.is_file():return match[0]
    digest=hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    name=f'{source.stem}.{digest}{source.suffix}'
    shutil.copyfile(source,args.out/'assets'/name)
    return f'assets/{name}'

markup=(ROOT/'index.html').read_text(encoding='utf-8').replace('__APP_ORIGIN__',args.app_origin)
markup=re.sub(r'assets/([A-Za-z0-9_.-]+)',version_asset,markup)
(args.out/'index.html').write_text(markup,encoding='utf-8')
shutil.copyfile(ROOT/'.htaccess',args.out/'.htaccess')
(args.out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://quehay.live/sitemap.xml\n')
if not (args.out/'sitemap.xml').exists():
    (args.out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://quehay.live/</loc></url></urlset>\n')
print(f'Landing built: {args.out.resolve()} | app origin: {args.app_origin}')
