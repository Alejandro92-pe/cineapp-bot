"""Redirect old public documents only; integration endpoints keep their origin."""
import os
from werkzeug.wrappers import Request, Response

OLD_HOST = 'cineapp-bot.onrender.com'
CANONICAL = 'https://app.quehay.live'
PAGES = frozenset({'/', '/cuenta', '/membresia', '/instalar', '/admin',
                   '/tv', '/tv/', '/tv/vincular'})


class CanonicalDocuments:
    def __init__(self, application, *, origin, local, mode='off'):
        if mode not in ('off', 'temporary', 'permanent'):
            raise ValueError('LEGACY_REDIRECT_MODE debe ser off, temporary o permanent.')
        self.application = application
        self.enabled = not local and origin == CANONICAL and mode != 'off'
        self.status = 301 if mode == 'permanent' else 302

    def __call__(self, environ, start_response):
        request = Request(environ)
        if (self.enabled and request.host == OLD_HOST and
                request.method in ('GET', 'HEAD') and request.path in PAGES):
            # Fixed destination; do not trust X-Forwarded-Host or a next/url parameter.
            query = environ.get('QUERY_STRING', '')
            target = CANONICAL + request.path + ('?' + query if query else '')
            response = Response(status=self.status, headers={
                'Location': target, 'Cache-Control': 'no-store',
                'Referrer-Policy': 'same-origin'})
            return response(environ, start_response)
        return self.application(environ, start_response)


def install(app):
    # Outermost layer also covers TV, whose own host check remains unchanged.
    app.wsgi_app = CanonicalDocuments(app.wsgi_app,
        origin=app.config['APP_ORIGIN'], local=app.config['SECURITY_LOCAL'],
        mode=os.getenv('LEGACY_REDIRECT_MODE', 'off'))
