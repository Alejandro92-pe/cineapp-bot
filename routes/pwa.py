"""Public installation resources. No private data or entitlement is cached."""
from flask import Blueprint, send_from_directory, current_app
from pathlib import Path


def pwa_routes():
    bp = Blueprint('pwa', __name__)
    assets = Path(__file__).resolve().parents[1]/'static/pwa'

    @bp.get('/manifest.webmanifest')
    def manifest():
        response = send_from_directory(assets, 'manifest.webmanifest', mimetype='application/manifest+json')
        response.headers['Cache-Control'] = 'no-cache'
        return response

    @bp.get('/sw.js')
    def worker():
        response = send_from_directory(assets, 'sw.js', mimetype='application/javascript')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Service-Worker-Allowed'] = '/'
        return response

    @bp.get('/instalar')
    def install():
        response = send_from_directory(assets, 'install.html')
        response.direct_passthrough = False
        markup = response.get_data(as_text=True).replace('<!--LOCAL_NOTICE-->',
            '')
        if current_app.config['SECURITY_LOCAL'] and not current_app.config.get('TELEGRAM_PREVIEW'):
            markup = markup.replace('https://telegram.org/js/telegram-web-app.js', '/static/telegram-local.js')
        response.set_data(markup)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @bp.get('/offline')
    def offline():
        response = send_from_directory(assets, 'offline.html')
        response.headers['Cache-Control'] = 'no-cache'
        return response

    return bp
