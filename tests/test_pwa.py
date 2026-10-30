from io import BytesIO
import re
from PIL import Image
import pytest
from conftest import send


def test_manifest_scope_icons_and_standalone_are_public(client):
    response=send(client,'/manifest.webmanifest',method='GET')
    assert response.status_code==200
    assert response.mimetype=='application/manifest+json'
    import json
    manifest=json.loads(response.data)
    assert manifest['id']==manifest['scope']==manifest['start_url']=='/'
    assert manifest['display']=='standalone'
    assert manifest['prefer_related_applications'] is False
    assert {icon['sizes'] for icon in manifest['icons']}=={'192x192','512x512'}
    assert any(icon['purpose']=='maskable' for icon in manifest['icons'])
    for icon in manifest['icons']:
        image=send(client,icon['src'],method='GET')
        assert image.status_code==200 and image.mimetype=='image/png'
        with Image.open(BytesIO(image.data)) as png:
            assert f'{png.width}x{png.height}'==icon['sizes']
            assert png.mode=='RGB'  # opaque maskable artwork, no transparent corners


def test_root_worker_is_javascript_with_unrestricted_app_scope_only(client):
    response=send(client,'/sw.js',method='GET')
    assert response.status_code==200 and response.mimetype=='application/javascript'
    assert response.headers['Service-Worker-Allowed']=='/'
    assert response.headers['Cache-Control']=='no-cache'
    assert "worker-src 'self'" in response.headers['Content-Security-Policy']
    assert "manifest-src 'self'" in response.headers['Content-Security-Policy']


@pytest.mark.parametrize('path',['/','/cuenta','/membresia','/instalar'])
def test_public_entry_pages_include_install_metadata(client,path):
    response=send(client,path,method='GET')
    assert response.status_code==200
    markup=response.get_data(as_text=True)
    assert 'href="/manifest.webmanifest"' in markup
    assert re.search(r'src="/static/pwa/install\.js(?:\?v=[^"\s]+)?"',markup)
    assert 'viewport-fit=cover' in markup
    assert 'theme-color' in markup


def test_offline_page_is_static_without_identity_or_payment_data(client):
    response=send(client,'/offline',method='GET')
    assert response.status_code==200
    markup=response.get_data(as_text=True)
    assert '<script' not in markup and '/api/' not in markup
    assert 'https://' not in markup
    assert 'necesitas conexión' in markup
    assert 'membresía' in markup


def test_installation_never_grants_access_or_relaxes_origin(client):
    for path in ['/instalar','/manifest.webmanifest','/sw.js','/offline']:
        assert send(client,path,method='GET').status_code==200
    assert send(client,'/api/download/1',method='GET').status_code==401
    assert send(client,'/api/playback/1',method='GET').status_code==401
    assert send(client,'/api/payments/mine',method='GET').status_code==401
    assert client.get('/sw.js',base_url='http://malicious.example').status_code==403


def test_install_page_has_clean_copy_and_keeps_isolated_telegram_stub(client):
    markup=send(client,'/instalar',method='GET').get_data(as_text=True)
    assert 'VISTA LOCAL' not in markup
    assert '/static/telegram-local.js' in markup
    assert 'https://telegram.org/js/telegram-web-app.js' not in markup


def test_production_install_template_has_no_local_demo_notice(client,system,monkeypatch):
    monkeypatch.setitem(system.app.config,'SECURITY_LOCAL',False)
    markup=send(client,'/instalar',method='GET').get_data(as_text=True)
    assert 'VISTA LOCAL' not in markup
    assert '<!--LOCAL_NOTICE-->' not in markup
