import pytest
from flask import Flask, jsonify
from werkzeug.test import Client
from werkzeug.wrappers import Response
from services.canonical_origin import CanonicalDocuments, CANONICAL, OLD_HOST, PAGES

OLD = 'https://' + OLD_HOST


def fixture_client(mode='temporary', local=False, origin=CANONICAL):
    app = Flask(__name__, static_folder=None)
    @app.route('/', defaults={'path':''}, methods=['GET','POST','OPTIONS'])
    @app.route('/<path:path>', methods=['GET','POST','OPTIONS'])
    def echo(path):
        from flask import request
        return jsonify(method=request.method, path=request.path,
                       body=request.get_data(as_text=True), host=request.host)
    return Client(CanonicalDocuments(app, origin=origin, local=local, mode=mode), Response)


@pytest.mark.parametrize('path', sorted(PAGES))
@pytest.mark.parametrize('method', ['GET','HEAD'])
@pytest.mark.parametrize('mode,status', [('temporary',302),('permanent',301)])
def test_only_documents_redirect_preserving_query(path,method,mode,status):
    r=fixture_client(mode).open(path+'?contenido=675&q=acci%C3%B3n&next=https%3A%2F%2Fevil.test',method=method,base_url=OLD)
    assert r.status_code==status
    assert r.headers['Location']==CANONICAL+path+'?contenido=675&q=acci%C3%B3n&next=https%3A%2F%2Fevil.test'
    assert r.headers['Cache-Control']=='no-store'
    assert 'Set-Cookie' not in r.headers


@pytest.mark.parametrize('path', ['/webhook/telegram','/webhook/buymeacoffee',
    '/webhook/paypal','/cron/verificar_vencimientos','/cron/publicar_contenido',
    '/cron/actualizar_imagenes','/api/auth/me','/api/auth/login','/api/download/1',
    '/api/playback/1','/tv/api/pair/start','/tv/api/phone/confirm',
    '/tv/api/play','/health','/static/app.js','/tv/assets/tv.js',
    '/version.json','/tv/version.json','/sw.js','/manifest.webmanifest',
    '/paypal/success','/paypal/cancel','/offline','/unknown'])
@pytest.mark.parametrize('method', ['GET','HEAD','POST','OPTIONS'])
def test_technical_routes_and_callbacks_are_not_redirected(path,method):
    r=fixture_client().open(path,method=method,base_url=OLD,data='unchanged')
    assert r.status_code==200 and 'Location' not in r.headers
    if method!='HEAD':assert r.json['body']=='unchanged' and r.json['method']==method


@pytest.mark.parametrize('method',['POST','OPTIONS'])
@pytest.mark.parametrize('path', sorted(PAGES))
def test_writes_to_documents_are_untouched(path,method):
    r=fixture_client().open(path,base_url=OLD,method=method,data='keep')
    assert r.status_code==200 and r.json['body']=='keep'


@pytest.mark.parametrize('host',[CANONICAL,'https://evil.test','https://'+OLD_HOST+'.evil.test'])
def test_no_loop_or_forwarded_host_trust(host):
    r=fixture_client().get('/',base_url=host,headers={'X-Forwarded-Host':OLD_HOST})
    assert r.status_code==200 and 'Location' not in r.headers


@pytest.mark.parametrize('kwargs',[{'mode':'off'},{'local':True},{'origin':'http://127.0.0.1:5030'}])
def test_safe_disabled_config(kwargs):
    assert fixture_client(**kwargs).get('/',base_url=OLD).status_code==200


def test_bad_mode_does_not_silently_activate():
    with pytest.raises(ValueError):fixture_client('yes')


def test_redirect_wraps_tv_before_its_host_boundary(system):
    from tv.integration import TVRouter
    def forbidden(environ,start_response):raise AssertionError('TV handler should not run')
    app=CanonicalDocuments(TVRouter(forbidden,forbidden),origin=CANONICAL,local=False,mode='temporary')
    assert Client(app,Response).get('/tv?kind=biblico',base_url=OLD).headers['Location']==CANONICAL+'/tv?kind=biblico'


def test_existing_sessions_downloads_and_owner_access_survive(system,client):
    import copy
    from conftest import tg_login, ORIGIN
    login=tg_login(client,5824989040)
    assert login.status_code==200
    before=copy.deepcopy(system.supabase_service.rows)
    wrapped=CanonicalDocuments(system.app,origin=CANONICAL,local=False,mode='temporary')
    c=Client(wrapped,Response)
    assert c.get('/',base_url=OLD).status_code==302
    assert client.get('/api/auth/me',base_url=ORIGIN).json['user']['telegram_id']==5824989040
    assert client.get('/api/playback/1',base_url=ORIGIN).status_code==200
    assert client.get('/api/download/1',base_url=ORIGIN).status_code==200
    assert system.supabase_service.rows==before
