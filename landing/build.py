"""Build a standalone static landing; never changes a server or DNS."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--app-origin', choices=['https://cineapp-bot.onrender.com', 'https://app.quehay.live','http://127.0.0.1:5014'], default='https://app.quehay.live')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
(args.out/'index.html').write_text((ROOT/'index.html').read_text(encoding='utf-8').replace('__APP_ORIGIN__',args.app_origin),encoding='utf-8')
shutil.copytree(ROOT/'assets',args.out/'assets',dirs_exist_ok=True)
shutil.copyfile(ROOT/'.htaccess',args.out/'.htaccess')
(args.out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://quehay.live/sitemap.xml\n')
if not (args.out/'sitemap.xml').exists():
    (args.out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://quehay.live/</loc></url></urlset>\n')
print(f'Landing built: {args.out.resolve()} | app origin: {args.app_origin}')
