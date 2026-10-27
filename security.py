"""Authentication boundary shared by the existing Flask routes and local preview."""
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import parse_qsl, urlsplit

import bcrypt
from flask import request, jsonify, g, send_from_directory
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from security_store import SecurityStore

OWNER_ID = 5824989040


def owner_access(account):
    """Only the server-verified owner's account has permanent viewing access."""
    return bool(account and account.get('telegram_id') == OWNER_ID)
COOKIE = "cine_session"
PUBLIC_POSTS = {"/api/contenido", "/api/auth/login", "/api/auth/register",
                "/api/auth/telegram", "/api/admin/login"}
ADMIN_PATHS = {"/aprobar_pago", "/admin_pedidos", "/marcar_entregado",
               "/renovar_membresia", "/estado_notificaciones", "/resetear_flags"}
USER_PATHS = {"/api/usuario", "/api/mis_pedidos", "/mis_pedidos", "/crear_pedido",
              "/crear_pago_tarjeta", "/api/paypal/crear_pago"}
CATALOG_FIELDS = {"id", "titulo", "tipo", "genero", "año", "imagen_url", "backdrop_url", "sinopsis", "trailer_url",
                    "rating", "tmdb_id", "destacado", "disponible", "orden_destacado", "fuente", "playback_unverified", "start_season"}


def admin_authenticated():
    session = getattr(g, "identity", None)
    return bool(session and session["admin"] and session["account"]["telegram_id"] == OWNER_ID)


def password_ok(password, encoded):
    try:
        if not isinstance(password, str) or not 1 <= len(password.encode()) <= 72:
            return False
        if not encoded or not encoded.startswith(("$2a$", "$2b$", "$2y$")):
            return False
        return bcrypt.checkpw(password.encode(), encoded.encode())
    except (ValueError, TypeError):
        return False


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) or len(password.encode()) > 72:
        raise ValueError("Usa al menos 12 caracteres y un máximo de 72 bytes.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def telegram_identity(raw, bot_token, now=None):
    if not isinstance(raw, str) or len(raw) > 16384 or not bot_token:
        raise ValueError("Identidad de Telegram inválida.")
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError("Parámetros duplicados.")
    supplied = data.pop("hash", "")
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, "\n".join(f"{k}={v}" for k,v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(expected, supplied):
        raise ValueError("Firma de Telegram inválida.")
    age = (time.time() if now is None else now) - int(data.get("auth_date", "0"))
    if age < -30 or age > 300:
        raise ValueError("Abre de nuevo la aplicación desde Telegram.")
    user = json.loads(data.get("user", "{}"))
    if type(user.get("id")) is not int or user["id"] <= 0 or user.get("is_bot"):
        raise ValueError("Usuario de Telegram inválido.")
    return user


def install_security(app, membership_checker):
    local = os.getenv("APP_MODE") == "local"
    preview = local and os.getenv("TELEGRAM_PREVIEW") == "true"
    origin = os.getenv("APP_ORIGIN", "http://127.0.0.1:5010" if local else "").rstrip("/")
    parsed = urlsplit(origin)
    if not parsed.netloc or parsed.path or (not local and parsed.scheme != "https"):
        raise RuntimeError("Configura APP_ORIGIN con el origen HTTPS de la aplicación.")
    if preview:
        from services.preview import validate_preview_origin
        validate_preview_origin(origin)
    if local and not preview and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("El modo local solo permite loopback.")
    db_url = os.getenv("SECURITY_DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("Configura SECURITY_DATABASE_URL; no se usan credenciales implícitas.")
    store = SecurityStore(db_url, local=local)
    app.extensions["security_store"] = store
    app.config.update(MAX_CONTENT_LENGTH=2*1024*1024, SECURITY_LOCAL=local, TELEGRAM_PREVIEW=preview, APP_ORIGIN=origin)

    def error(message, status, code=None):
        return jsonify(error=message,**({'code':code} if code else {})), status

    def data():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError("Se requiere un objeto JSON.")
        return value

    def limited(identifier):
        # Never accept a client-supplied X-Forwarded-For as the IP.
        ip = request.remote_addr or "unknown"
        return (store.allow_attempt("ip:"+ip, 100) and
                store.allow_attempt("identity:"+str(identifier).lower(), 10))

    def account_view(account):
        return {k: account.get(k) for k in ("id", "email", "name", "telegram_id")}

    def issue(account, admin=False):
        ttl = 3600 if admin else 43200
        token, csrf = store.new_session(account["id"], ttl, admin, request.cookies.get(COOKIE))
        response = jsonify(success=True, authenticated=True, user=account_view(account),
                           is_admin=admin, csrf_token=csrf)
        response.set_cookie(COOKIE, token, max_age=ttl, secure=not local or preview,
                            httponly=True, samesite="Lax", path="/")
        return response

    @app.before_request
    def boundary():
        # Host validation also prevents DNS rebinding of the local preview.
        if request.host != parsed.netloc:
            return error("Origen no permitido.", 403)
        path = request.path
        if preview and (path.startswith('/cron/') or path.startswith('/webhook/') or path == '/'+os.getenv('BOT_TOKEN', '__unset__')):
            return error('Integración de producción deshabilitada en la prueba.', 403)
        if preview and (path.startswith('/api/admin/vimeus') or path in {'/api/admin/importar_tmdb', '/api/admin/importar_temporadas'}):
            return error('Esta prueba usa una copia del catálogo. La importación real requiere configurar Vimeus Listing por separado.', 503)
        if request.content_length and request.content_length > 256*1024 and path != "/api/admin/payments/qr":
            return error("Solicitud demasiado grande.", 413)
        g.identity = store.session(request.cookies.get(COOKIE))
        if request.endpoint is None:
            return None
        if path.startswith("/cron/"):
            secret = os.getenv("CRON_SECRET", "")
            if len(secret) < 32:
                return error("Cron pendiente de configuración.", 503)
            if not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer "+secret):
                return error("No autorizado.", 401)
            return None
        if path.startswith("/webhook/") or path == "/"+os.getenv("BOT_TOKEN", "__unset__"):
            if path in {"/webhook/telegram", "/"+os.getenv("BOT_TOKEN", "__unset__")}:
                secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
                if len(secret) < 32 or not hmac.compare_digest(
                    request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret):
                    return error("No autorizado.", 401)
            return None  # Payment handlers perform their own cryptographic verification.
        if request.method == "OPTIONS":
            return error("Solicitudes entre orígenes deshabilitadas.", 403)
        if request.method not in ("GET", "HEAD"):
            if request.headers.get("Origin") != origin or not request.is_json:
                return error("Origen o formato no permitido.", 403)
            if not isinstance(request.get_json(silent=True), dict):
                return error("Se requiere un objeto JSON.", 400)
            if path not in PUBLIC_POSTS:
                if not g.identity:
                    return error("Inicia sesión para continuar.", 401, 'auth_required')
                if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), g.identity["csrf"]):
                    return error("La sesión necesita actualizarse.", 403)
        if path in {"/", "/admin", "/cuenta", "/membresia", "/instalar", "/offline", "/sw.js", "/manifest.webmanifest", "/api/payments/config", "/health", "/api/planes", "/api/tendencias",
                    "/api/auth/me", "/api/top10", "/paypal/success", "/paypal/cancel"} or path.startswith(("/static/", "/api/payments/qr/")) or path in PUBLIC_POSTS:
            return None
        if path.startswith("/api/admin/") or path in ADMIN_PATHS:
            if not admin_authenticated():
                return error("Se requiere una sesión de administrador.", 403)
            return None
        if path.startswith(("/api/temporadas/", "/api/episodios/")):
            return None  # Public season metadata; links are removed below.
        if not g.identity:
            return error("Inicia sesión para continuar.", 401, 'auth_required')
        if path in USER_PATHS:
            body = data()
            actual = g.identity["account"].get("telegram_id")
            if not actual:
                return error("Vincula Telegram para recuperar tu acceso anterior. Los cobros web llegan en la siguiente fase.", 409)
            if "telegram_id" in body and str(body["telegram_id"]) != str(actual):
                return error("No puedes acceder a otra cuenta.", 403)
            # Routes receive only the verified identity, never the asserted client ID.
            body["telegram_id"] = actual
        if path.startswith("/api/playback/") or path == "/api/config/vimeus_key":
            if not membership_checker(g.identity["account"].get("telegram_id")):
                return error("Tu acceso no está activo o ha vencido.", 403, 'membership_required')

    @app.after_request
    def harden(response):
        response.headers.pop("Access-Control-Allow-Origin", None)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "origin"
        # Mini Apps must remain embeddable by Telegram Web.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; connect-src 'self'; frame-src https://vimeus.com https://www.vimeus.com https://www.youtube-nocookie.com https://ok.ru; "
            "worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self' https://web.telegram.org")
        if not local:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/") or request.path in ADMIN_PATHS | USER_PATHS:
            response.headers["Cache-Control"] = "no-store"
        if response.is_json and response.status_code < 400 and (
                request.path in ("/api/contenido", "/api/tendencias") or request.path.startswith("/api/temporadas/")):
            payload = response.get_json()
            if request.path in ("/api/contenido", "/api/tendencias"):
                def clean(row):
                    result = {k:v for k,v in row.items() if k in CATALOG_FIELDS}
                    result["has_download"] = bool(row.get("descarga"))
                    return result
                if isinstance(payload, list):
                    payload = [clean(row) for row in payload]
                elif isinstance(payload, dict):
                    payload["data"] = [clean(row) for row in payload.get("data", [])]
                response.set_data(app.json.dumps(payload))
            if request.path.startswith("/api/temporadas/"):
                for row in payload.get("temporadas", []):
                    row.pop("enlace", None)
                response.set_data(app.json.dumps(payload))
        if response.status_code >= 500 and response.is_json:
            response.set_data(app.json.dumps({"error":"Servicio temporalmente no disponible. Intenta de nuevo."}))
        return response

    @app.errorhandler(Exception)
    def safe_exception(exc):
        if isinstance(exc, HTTPException):
            return error(exc.name, exc.code)
        # Do not print request bodies, tokens, passwords or exception strings.
        app.logger.error("Request failed: %s", type(exc).__name__)
        return error("Servicio temporalmente no disponible.", 503)

    @app.get("/health")
    def health():
        return jsonify(status="ok", mode="local" if local else "production")

    @app.get("/cuenta")
    def account_page():
        response = send_from_directory("static", "account.html")
        if local and not preview:
            response.direct_passthrough = False
            response.set_data(response.get_data(as_text=True).replace(
                "https://telegram.org/js/telegram-web-app.js", "/static/telegram-local.js"))
        return response

    @app.get("/api/auth/me")
    def me():
        if not g.identity:
            return jsonify(authenticated=False, local=local, preview=preview)
        return jsonify(authenticated=True, user=account_view(g.identity["account"]),
            is_admin=admin_authenticated(), csrf_token=g.identity["csrf"], local=local, preview=preview)

    @app.post("/api/auth/register")
    def register():
        body = data()
        email = str(body.get("email", "")).strip().lower()
        if not limited(email):
            return error("Demasiados intentos. Espera 15 minutos.", 429)
        name = str(body.get("name", "")).strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email)>254 or not 1<=len(name)<=80:
            return error("Revisa tu nombre y correo.", 400)
        try:
            hashed = password_hash(body.get("password"))
            account = store.create_account(name, email, hashed)
        except ValueError as exc:
            return error(str(exc), 400)
        except IntegrityError:
            return error("No se pudo crear la cuenta. Prueba iniciar sesión.", 409)
        # Email is an identifier, not proof of ownership of an existing paid account.
        return issue(account)

    @app.post("/api/auth/login")
    def login():
        body = data()
        email = str(body.get("email", "")).strip().lower()
        if not limited(email):
            return error("Demasiados intentos. Espera 15 minutos.", 429)
        account = store.account(email=email)
        # Constant-cost fallback avoids a fast path for unknown addresses.
        encoded = account["password_hash"] if account and account["password_hash"] else app.config["DUMMY_PASSWORD_HASH"]
        valid = password_ok(body.get("password"), encoded)
        if not valid or not account or not account["password_hash"]:
            return error("Correo o contraseña incorrectos.", 401)
        return issue(account)  # Administrator elevation requires a separate proof.

    @app.post("/api/auth/telegram")
    def telegram_login():
        body = data()
        if not store.allow_attempt("telegram:"+(request.remote_addr or "unknown"), 60):
            return error("Demasiados intentos.", 429)
        try:
            user = telegram_identity(body.get("init_data"), os.getenv("BOT_TOKEN", ""))
        except (ValueError, TypeError, KeyError):
            return error("No se pudo verificar Telegram. Abre de nuevo la Mini App.", 401)
        # When already logged in, explicitly link; never silently switch accounts.
        if g.identity:
            if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), g.identity["csrf"]):
                return error("Actualiza tu sesión.", 403)
            account = g.identity["account"]
            if account["telegram_id"] not in (None, user["id"]):
                return error("La cuenta ya tiene otro Telegram vinculado.", 409)
            if account["telegram_id"] is None:
                try:
                    if not store.link_telegram(account["id"], user["id"]):
                        return error("La vinculación cambió. Inicia sesión de nuevo.", 409)
                except IntegrityError:
                    return error("Ese Telegram ya está vinculado. Accede con esa cuenta; no se fusionan automáticamente.", 409)
                account = store.account(id=account["id"])
        else:
            account = store.account(telegram_id=user["id"])
            if not account:
                try:
                    account = store.create_account(str(user.get("first_name", "Usuario"))[:80], telegram_id=user["id"])
                except IntegrityError:
                    account = store.account(telegram_id=user["id"])
        return issue(account, admin=user["id"] == OWNER_ID)

    @app.post("/api/auth/logout")
    def logout():
        store.revoke(request.cookies.get(COOKIE))
        response = jsonify(success=True)
        response.delete_cookie(COOKIE, path="/", secure=not local or preview, httponly=True, samesite="Lax")
        return response

    @app.post("/api/auth/password")
    def change_password():
        body = data()
        account = g.identity["account"]
        if not limited(account["id"]):
            return error("Demasiados intentos.", 429)
        if account["password_hash"] and not password_ok(body.get("current_password"), account["password_hash"]):
            return error("Contraseña actual incorrecta.", 401)
        if not account["password_hash"]:
            return error("Esta cuenta usa Telegram. Accede desde Telegram.", 409)
        try:
            hashed = password_hash(body.get("password"))
        except ValueError as exc:
            return error(str(exc), 400)
        store.change_password(account["id"], hashed)
        return issue(store.account(id=account["id"]))

    def admin_login():
        body = data()
        if not limited("admin"):
            return error("Demasiados intentos. Espera 15 minutos.", 429)
        encoded = os.getenv("ADMIN_PASSWORD_HASH") or os.getenv("ADMIN_PASSWORD", "")
        if not encoded.startswith(("$2a$", "$2b$", "$2y$")):
            return error("Configura el hash bcrypt del administrador.", 503)
        valid = password_ok(body.get("password"), encoded)
        if str(body.get("admin_id")) != str(OWNER_ID) or not valid:
            return error("ID o contraseña incorrectos.", 401)
        account = store.account(telegram_id=OWNER_ID)
        if not account:
            try:
                account = store.create_account("Ale", telegram_id=OWNER_ID)
            except IntegrityError:
                account = store.account(telegram_id=OWNER_ID)
        return issue(account, admin=True)

    app.config["DUMMY_PASSWORD_HASH"] = bcrypt.hashpw(os.urandom(32), bcrypt.gensalt()).decode()
    app.extensions["admin_login"] = admin_login
    return store
