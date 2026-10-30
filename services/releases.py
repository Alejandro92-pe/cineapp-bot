"""Public build identifier and opt-in reload notice; no database or account reads."""
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from flask import jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]

@lru_cache(maxsize=1)
def version():
    commit = os.getenv('RENDER_GIT_COMMIT', '')
    if commit:
        return hashlib.sha256(commit.encode()).hexdigest()[:20]
    digest = hashlib.sha256()
    for folder in ('static', 'tv', 'services', 'routes'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.suffix in ('.js', '.css', '.html', '.py'):
                digest.update(path.relative_to(ROOT).as_posix().encode())
                digest.update(path.read_bytes())
    for name in ('main.py', 'security.py'):
        digest.update((ROOT/name).read_bytes())
    return digest.hexdigest()[:20]

def install(app, tv=False):
    build = version()
    endpoint = '/tv/version.json' if tv else '/version.json'
    assets = '/tv/update-notice' if tv else '/static/updates/notice'
    pages = {'/tv', '/tv/', '/tv/vincular'} if tv else {'/', '/cuenta', '/membresia', '/instalar'}
    @app.before_request
    def fresh_document():
        if request.path in pages:
            # Static template timestamps do not represent an injected build ID.
            request.environ.pop('HTTP_IF_NONE_MATCH', None)
            request.environ.pop('HTTP_IF_MODIFIED_SINCE', None)
    @app.get(endpoint)
    def release_version():
        response = jsonify(version=build)
        response.headers['Cache-Control'] = 'no-store'
        return response
    if tv:
        app.add_url_rule(assets+'.js', 'update_script', lambda: send_from_directory(ROOT/'static/updates', 'notice.js'))
        app.add_url_rule(assets+'.css', 'update_style', lambda: send_from_directory(ROOT/'static/updates', 'notice.css'))
    @app.after_request
    def notice(response):
        if request.path in pages and response.status_code == 200 and response.mimetype == 'text/html':
            response.direct_passthrough = False
            head = (f'<meta name="qh-release" content="{build}" data-endpoint="{endpoint}">'
                    f'<link rel="stylesheet" href="{assets}.css"><script src="{assets}.js" defer></script>')
            response.set_data(response.get_data(as_text=True).replace('</head>', head+'</head>', 1))
            response.headers['Cache-Control'] = 'no-store'
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
        return response
