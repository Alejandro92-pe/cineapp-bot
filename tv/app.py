"""Local-only TV application. Deliberately not mounted on main.py or Render."""
import hmac
import time
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, send_from_directory, g
from werkzeug.exceptions import HTTPException
from tv.store import PairingStore
from tv.catalog import Catalog, KINDS
from security import password_ok, owner_access
from billing.store import BillingStore

ROOT = Path(__file__).resolve().parent
PHONE_COOKIE, TV_COOKIE, PAIR_COOKIE = 'qh_tv_phone_local', 'qh_tv_device_local', 'qh_tv_pair_local'


def create_app(database, security, origin='http://127.0.0.1:5020'):
    parsed=urlsplit(origin)
    if not security.local or parsed.hostname not in ('127.0.0.1','localhost') or parsed.scheme!='http' or parsed.path:
        raise RuntimeError('Esta fase TV solo admite una base aislada y un servidor loopback.')
    app=Flask(__name__,static_folder=str(ROOT/'static'),static_url_path='/tv/assets')
    app.config.update(MAX_CONTENT_LENGTH=8192)
    pairing, catalog, billing = PairingStore(security), Catalog(database), BillingStore(security)
    app.extensions.update(tv_pairing=pairing,tv_catalog=catalog)

    def error(text,status):return jsonify(error=text),status
    def active(account):return bool(account and (owner_access(account) or billing.expiry(account['id'])>time.time()))
    def cookie(response,name,value,age):
        response.set_cookie(name,value,max_age=age,httponly=True,samesite='Strict',secure=False,path='/tv')
        return response
    def limit(key,count,seconds=60):return security.allow_attempt('tv:'+key+':'+(request.remote_addr or ''),count,seconds)

    @app.before_request
    def boundary():
        if request.host != parsed.netloc:return error('Origen no permitido.',403)
        g.device=pairing.session(request.cookies.get(TV_COOKIE))
        g.phone=security.session(request.cookies.get(PHONE_COOKIE))
        if request.method not in ('GET','HEAD'):
            if request.headers.get('Origin')!=origin or not request.is_json or not isinstance(request.get_json(silent=True),dict):
                return error('Solicitud no permitida.',403)
        if request.path.startswith('/tv/api/phone/') and request.path not in ('/tv/api/phone/login','/tv/api/phone/me'):
            if not g.phone:return error('Inicia sesión desde tu celular.',401)
            if request.method=='POST' and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),g.phone['csrf']):
                return error('Actualiza la sesión del celular.',403)
        if request.path in ('/tv/api/play','/tv/api/unlink'):
            if not g.device:return error('Vincula tu cuenta para continuar.',401)
            if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),g.device['csrf']):return error('Actualiza la sesión del televisor.',403)

    @app.after_request
    def harden(r):
        r.headers['Cache-Control']='no-store'
        r.headers['Referrer-Policy']='origin'
        r.headers['X-Content-Type-Options']='nosniff'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://image.tmdb.org; connect-src 'self'; frame-src https://videoapi.la https://ok.ru; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        r.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        return r

    @app.errorhandler(Exception)
    def safe_error(exc):
        if isinstance(exc,HTTPException):return error('Página no disponible.',exc.code)
        app.logger.error('TV request failed: %s',type(exc).__name__)
        return error('No pudimos completar la solicitud. Inténtalo de nuevo.',503)

    @app.get('/tv')
    @app.get('/tv/')
    def home():return send_from_directory(ROOT/'static','index.html')
    @app.get('/tv/vincular')
    def phone_page():return send_from_directory(ROOT/'static','link.html')
    @app.get('/tv/brand')
    def brand():return send_from_directory(ROOT.parent/'static','logo-que-hay-live.png')
    @app.get('/tv/api/me')
    def me():
        account=security.account(id=g.device['account_id']) if g.device else None
        return jsonify(linked=bool(account),name=account['name'] if account else None,active=active(account),csrf=g.device['csrf'] if account else None)

    @app.post('/tv/api/pair/start')
    def start():
        if not limit('start',10,600):return error('Espera unos minutos antes de generar otro código.',429)
        token,code,expiry=pairing.start(request.cookies.get(PAIR_COOKIE))
        return cookie(jsonify(code=code,expires_at=expiry,url=origin+'/tv/vincular'),PAIR_COOKIE,token,600)
    @app.post('/tv/api/pair/poll')
    def poll():
        if not limit('poll',40):return error('Espera unos segundos.',429)
        state,token=pairing.poll(request.cookies.get(PAIR_COOKIE))
        r=jsonify(state=state)
        if token:
            cookie(r,TV_COOKIE,token,604800)
            r.delete_cookie(PAIR_COOKIE,path='/tv')
        return r
    @app.post('/tv/api/unlink')
    def unlink():
        pairing.revoke(request.cookies.get(TV_COOKIE));r=jsonify(success=True);r.delete_cookie(TV_COOKIE,path='/tv');return r

    @app.post('/tv/api/phone/login')
    def login():
        if not limit('login',8,900):return error('Demasiados intentos. Espera unos minutos.',429)
        body=request.get_json();email=str(body.get('email','')).strip().lower()
        account=security.account(email=email)
        if not account or not password_ok(body.get('password'),account.get('password_hash')):return error('Correo o contraseña incorrectos.',401)
        token,csrf=security.new_session(account['id'],3600,old_token=request.cookies.get(PHONE_COOKIE))
        return cookie(jsonify(name=account['name'],csrf=csrf),PHONE_COOKIE,token,3600)
    @app.get('/tv/api/phone/me')
    def phone_me():return jsonify(name=g.phone['account']['name'] if g.phone else None,csrf=g.phone['csrf'] if g.phone else None)
    @app.post('/tv/api/phone/confirm')
    def confirm():
        if not limit('confirm',10,600):return error('Demasiados intentos. Espera unos minutos.',429)
        if not pairing.approve(request.get_json().get('code',''),g.phone['account']['id']):return error('Código vencido, utilizado o incorrecto.',400)
        return jsonify(success=True)
    @app.post('/tv/api/phone/revoke')
    def revoke():pairing.revoke_account(g.phone['account']['id']);return jsonify(success=True)

    @app.get('/tv/api/home')
    def feed():return jsonify(rows=[{'kind':k,'title':title,**catalog.titles(k)} for k,title in KINDS.items()])
    @app.get('/tv/api/catalog')
    def search():
        kind=request.args.get('kind') or None;page=request.args.get('page',1,type=int)
        if kind not in (None,*KINDS) or page is None or not 1<=page<=500:return error('Página no válida.',400)
        return jsonify(catalog.titles(kind,request.args.get('q','')[:80],page))
    @app.get('/tv/api/title/<int:cid>')
    def title(cid):
        item=catalog.item(cid)
        return jsonify(item=item,seasons=catalog.seasons(cid)) if item else error('Título no disponible.',404)
    @app.get('/tv/api/episodes/<int:cid>/<int:sid>')
    def episodes(cid,sid):
        page=request.args.get('page',1,type=int)
        if page is None or not 1<=page<=1000:return error('Página no válida.',400)
        result=catalog.episodes(cid,sid,page)
        return jsonify(result) if result else error('Temporada no disponible.',404)
    @app.post('/tv/api/play')
    def play():
        if not active(security.account(id=g.device['account_id'])):return error('Tu cuenta no tiene acceso activo. Revísala desde tu celular.',403)
        body=request.get_json();cid=body.get('id');eid=body.get('episode')
        if type(cid) is not int or (eid is not None and type(eid) is not int):return error('Título o episodio no válido.',400)
        source=catalog.source(cid,eid)
        if not source:return error('Este video todavía no está disponible en TV.',404)
        return jsonify(**source,next=catalog.next_episode(cid,eid) if eid else None)
    return app
