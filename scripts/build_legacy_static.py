"""Export public WordPress content to static HTML without restoring MySQL.

This is an offline preparation step: it does not publish or activate redirects.
Only published posts and public taxonomy data are read from the saved SQL file.
"""
import argparse
import csv
import html
import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape

from prepare_legacy_seo import rows


class PublicText(HTMLParser):
    """Keep content semantics while excluding embeds, forms, scripts and styles."""
    allowed = {'p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'blockquote'}
    blocked = {'script', 'style', 'iframe', 'form', 'object', 'svg', 'noscript', 'button', 'select', 'textarea'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.depth = 0
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            host = urlsplit(dict(attrs).get('href', '')).hostname
            external = host is not None and host not in {'quehay.live', 'www.quehay.live'}
            self.anchors.append(external)
            if external:
                self.depth += 1
        if tag in self.blocked:
            self.depth += 1
        if not self.depth and tag in self.allowed:
            self.output.append('<' + tag + '>')

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchors:
            if self.anchors.pop():
                self.depth = max(0, self.depth - 1)
        elif tag in self.blocked:
            self.depth = max(0, self.depth - 1)
        elif not self.depth and tag in self.allowed and tag != 'br':
            self.output.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.depth:
            self.output.append(html.escape(re.sub(r'\[[^\]]*\]', '', data)))


def clean(value):
    parser = PublicText()
    parser.feed(value or '')
    return ''.join(parser.output)


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def build(sql_file, inventory, matches_file, destination, app_origin='https://app.quehay.live'):
    sql = sql_file.read_text(encoding='utf-8-sig')
    allowed_types = {'page', 'post', 'amy_movie', 'amy_tvshow', 'amy_season', 'amy_actor'}
    posts = {p['ID']: p for p in rows(sql, 'wpwz_posts')
             if p['post_status'] == 'publish' and p['post_type'] in allowed_types}
    by_slug = {(p['post_type'], unquote(p['post_name'])): p for p in posts.values()}
    terms = {p['term_id']: p for p in rows(sql, 'wpwz_terms')}
    tax = {(t['taxonomy'], unquote(terms[t['term_id']]['slug'])): t
           for t in rows(sql, 'wpwz_term_taxonomy') if t['term_id'] in terms}
    members = defaultdict(list)
    for rel in rows(sql, 'wpwz_term_relationships'):
        if rel['object_id'] in posts:
            members[rel['term_taxonomy_id']].append(posts[rel['object_id']])
    with inventory.open(encoding='utf-8-sig') as f:
        paths = {unquote(urlsplit(r['origen']).path): r['origen'] for r in csv.DictReader(f)}
    with matches_file.open(encoding='utf-8-sig') as f:
        matches = {unquote(urlsplit(r['origen']).path): r for r in csv.DictReader(f)}
    post_urls = {}
    for path in paths:
        parts = path.strip('/').split('/')
        post = by_slug.get((parts[0], parts[-1]))
        if post:
            post_urls[post['ID']] = path
    catalog_posts = sorted((p for p in posts.values() if p['ID'] in post_urls
                            and p['post_type'] in {'amy_movie', 'amy_tvshow'}),
                           key=lambda p: p['post_title'].casefold())
    origin = app_origin.rstrip('/')
    generated, unresolved, excluded = [], [], []

    def listing(items):
        return '<ul class="archive-list">' + ''.join(
            '<li><a href="' + html.escape(post_urls[p['ID']], quote=True) + '">' +
            html.escape(p['post_title']) + '</a></li>' for p in items if p['ID'] in post_urls) + '</ul>'

    for path, url in paths.items():
        if path == '/' or path.startswith('/cdn-cgi/'):
            excluded.append(path)
            continue
        # Directory URLs without a trailing slash redirect to the same page.
        # Publish only the final canonical form in the sitemap.
        url = url.rstrip('/') + '/'
        parts = path.strip('/').split('/')
        typ, slug = parts[0], parts[-1]
        post = by_slug.get((typ, slug)) or by_slug.get(('page', slug))
        if not post and typ.isdigit():
            post = by_slug.get(('post', slug))
        term = tax.get((typ, slug))
        title, content = '', ''
        target, label = origin + '/', 'Explorar el catálogo actual'
        noindex = False
        if post:
            title = post['post_title']
            if post['post_type'] == 'page' and slug not in {'politicas-de-privacidad', 'terminos-y-condiciones', 'dmca'}:
                if slug in {'membresias', 'iniciar-sesion-y-registro'}:
                    content = '<p>Consulta el acceso y las instrucciones actualizadas en nuestra aplicación.</p>'
                    target = origin + ('/membresia' if slug == 'membresias' else '/cuenta')
                    label = 'Ver acceso mensual' if slug == 'membresias' else 'Entrar a mi cuenta'
                elif slug in {'buscar', 'discusion'}:
                    content = '<p>Encuentra películas y series en el catálogo de Qué Hay Cine.</p>'
                    noindex = True
                else:
                    content = listing(catalog_posts)
            else:
                content = clean(post['post_content'] or post['post_excerpt'])
                if post['post_type'] in {'amy_movie', 'amy_tvshow'}:
                    match = matches.get(path, {})
                    if match.get('app_id'):
                        target = origin + '/?contenido=' + match['app_id']
                        label = 'Abrir esta ficha en Qué Hay'
        elif term:
            title = terms[term['term_id']]['name']
            content = clean(term['description']) + listing(members[term['term_taxonomy_id']])
        elif slug == 'feed':
            excluded.append(path)
            continue
        else:
            unresolved.append(path)
            continue
        description = plain(content)[:155] or title + ' · Qué Hay Cine'
        safe_path = destination.joinpath(*parts)
        if not safe_path.resolve().is_relative_to(destination.resolve()) or any(p in {'.', '..'} for p in parts):
            raise ValueError('Unsafe output path')
        safe_path.mkdir(parents=True, exist_ok=True)
        page = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | Qué Hay Cine</title><meta name="description" content="{html.escape(description, quote=True)}"><link rel="canonical" href="{html.escape(url, quote=True)}"><meta name="robots" content="{'noindex,follow' if noindex else 'index,follow'}"><link rel="stylesheet" href="/assets/landing.css"><link rel="stylesheet" href="/assets/archive.css"></head><body><header class="header wrap"><a class="brand" href="/" aria-label="Qué Hay Cine, inicio"><img src="/assets/brand-face.png" alt="" width="34" height="34"><span>Qué Hay</span></a><a class="account" href="{origin}/cuenta">Mi cuenta ↗</a></header><main class="wrap archive"><p class="eyebrow">QUÉ HAY CINE</p><h1>{html.escape(title)}</h1><a class="button primary" href="{html.escape(target, quote=True)}">{label} ↗</a><article>{content}</article></main><footer class="footer wrap"><a href="/">Inicio</a><a href="/politicas-de-privacidad/">Privacidad</a><a href="/terminos-y-condiciones/">Términos</a><a href="/dmca/">DMCA</a></footer></body></html>'''
        (safe_path/'index.html').write_text(page, encoding='utf-8')
        generated.append({'path': path, 'url': url, 'title': title, 'indexable': not noindex})
    (destination/'assets/archive.css').write_text('''.archive{max-width:980px;padding:55px 0 75px}.archive h1{font-size:clamp(32px,5vw,60px);letter-spacing:-1.5px;overflow-wrap:anywhere}.archive article{margin-top:48px;color:var(--muted);font-size:17px;line-height:1.85}.archive article h2,.archive article h3{color:var(--ink);margin-top:35px}.archive-list{list-style:none;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 30px}.archive-list a{display:block;border-bottom:1px solid var(--line);padding:12px 0}.archive-list a:hover{color:var(--blue)}@media(max-width:700px){.archive-list{grid-template-columns:1fr}.archive article{font-size:16px}}''', encoding='utf-8')
    urls = list(dict.fromkeys(['https://quehay.live/'] + [r['url'] for r in generated if r['indexable']]))
    (destination/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>'+escape(url)+'</loc></url>' for url in urls) + '</urlset>', encoding='utf-8')
    report = {'generated': len(generated), 'unresolved': unresolved, 'excluded': excluded,
              'redirects_activated': 0, 'database_restored': False, 'pages': generated}
    (destination.parent/'legacy-static-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'pages'}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sql', type=Path)
    ap.add_argument('inventory', type=Path)
    ap.add_argument('matches', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--app-origin', choices=['https://app.quehay.live', 'https://cineapp-bot.onrender.com'], default='https://app.quehay.live')
    a = ap.parse_args()
    build(a.sql, a.inventory, a.matches, a.out, a.app_origin)
