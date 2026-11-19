"""Archive password shown before a download, chosen by the site that hosts the file.

The rules live in catalog_cache (text payload) with an expiry far in the future, so the
cache clean-up never removes them and no new table or migration is needed.
"""
import json
import re
from urllib.parse import urlsplit
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from services.catalog_jobs import cache

KEY = 'settings:download_passwords'
FOREVER = 253402300799.0  # 31/12/9999: catalog clean-up deletes only expired cache rows
TORRENT = 'torrent'       # special site name: .torrent files and torrent hosts
DEFAULT = {
    'rules': [
        {'site': 'drive.google.com', 'password': 'quehay.live'},
        {'site': 'docs.google.com', 'password': 'quehay.live'},
        {'site': 'mediafire.com', 'password': 'cc'},
        {'site': 'megaup.net', 'password': ''},
        {'site': TORRENT, 'password': ''},
    ],
    'default': 'cc',
}
SITE = re.compile(r'^(torrent|[a-z0-9-]+(\.[a-z0-9-]+)+)$')


def clean(data):
    """Validate an admin edit. Empty password means 'no password' for that site."""
    if not isinstance(data, dict) or not isinstance(data.get('rules'), list) or len(data['rules']) > 30:
        raise ValueError('Envía una lista de sitios (máximo 30).')
    rules, seen = [], set()
    for row in data['rules']:
        if not isinstance(row, dict):
            raise ValueError('Cada regla necesita un sitio y una contraseña.')
        site = str(row.get('site', '')).strip().lower().removeprefix('www.')
        password = str(row.get('password', '')).strip()
        if not site and not password:
            continue
        if not SITE.match(site) or len(site) > 100:
            raise ValueError(f'«{site or "vacío"}» no es un sitio válido. Usa solo el dominio, por ejemplo mediafire.com.')
        if len(password) > 100:
            raise ValueError('La contraseña admite hasta 100 caracteres.')
        if site in seen:
            raise ValueError(f'El sitio {site} está repetido.')
        seen.add(site)
        rules.append({'site': site, 'password': password})
    default = str(data.get('default', '')).strip()
    if len(default) > 100:
        raise ValueError('La contraseña admite hasta 100 caracteres.')
    return {'rules': rules, 'default': default}


def load(engine):
    with engine.connect() as c:
        raw = c.execute(select(cache.c.payload).where(cache.c.key == KEY)).scalar_one_or_none()
    try:
        return clean(json.loads(raw)) if raw else json.loads(json.dumps(DEFAULT))
    except (ValueError, TypeError):
        return json.loads(json.dumps(DEFAULT))


def save(engine, local, data):
    value = clean(data)
    ins = sqlite_insert if local else pg_insert
    payload = json.dumps(value, ensure_ascii=False)
    with engine.begin() as c:
        c.execute(ins(cache).values(key=KEY, payload=payload, expires=FOREVER)
                  .on_conflict_do_update(index_elements=[cache.c.key], set_={'payload': payload, 'expires': FOREVER}))
    return value


def is_torrent(url):
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    return parts.path.lower().endswith('.torrent') or 'torrent' in host


def password_for(url, rules):
    """The password for this link, or '' when the file has none."""
    parts = urlsplit(url or '')
    host = (parts.hostname or '').lower()
    for rule in rules['rules']:
        site = rule['site']
        if (site == TORRENT and is_torrent(url)) or (site != TORRENT and (host == site or host.endswith('.' + site))):
            return rule['password']
    return rules['default']
