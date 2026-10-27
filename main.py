from flask import Flask, request, jsonify, send_from_directory, g, has_request_context
import os
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client
from datetime import datetime, timedelta, timezone
import time
import hmac
import hashlib
import re
import requests
import threading
from security import OWNER_ID, install_security, admin_authenticated, owner_access
from urllib.parse import urlencode, urlsplit

# ============ VARIABLES DE ENTORNO ============
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# El propietario es el único administrador, incluso con un entorno antiguo.
ADMIN_ID = OWNER_ID
ADMIN_IDS = {OWNER_ID}

SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

LOCAL_MODE = os.getenv("APP_MODE") == "local"
if LOCAL_MODE:
    from local_support import local_database, LocalBot
    supabase_service = local_database
else:
    supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def check_admin(data):
    """El ID recibido no autoriza: se exige una sesión verificada."""
    return admin_authenticated()

def is_admin(user_id):
    """Verifica si un user_id de Telegram es alguno de los admins."""
    try:
        return int(user_id) in ADMIN_IDS
    except (ValueError, TypeError):
        return False

# Contraseña del panel admin (static/admin.html), validada en backend.
# Config esto en Render como variable de entorno ADMIN_PASSWORD.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

supabase = supabase_service if LOCAL_MODE else create_client(SUPABASE_URL, SUPABASE_KEY)
bot = LocalBot() if LOCAL_MODE else telebot.TeleBot(BOT_TOKEN)

BOT_USERNAME = os.getenv("BOT_USERNAME", "Popcornqh_admin_bot")

# Zona horaria de Lima (UTC-5)
LIMA_TZ = timezone(timedelta(hours=-5))

# ============ IDs DE CANALES ============
GRUPO_SOPORTE_ID   = -1003805629374
CANAL_PELICULAS_ID = -1003890553566
CANAL_SERIES_ID    = -1003879512007
GRUPO_CONTENIDO_ID = -1002991571573
CANAL_ANIME_ID     = int(os.getenv("CANAL_ANIME_ID", "0"))
CANAL_PUBLICO_ID   = "@mejoresanimesenlatino"
CANAL_PRIVADO_ID   = -1002503337168

MINIAPP_URL = os.getenv("APP_ORIGIN", "https://cineapp-bot.onrender.com").rstrip("/")
BMC_URL     = MINIAPP_URL + "/membresia"
BMC_LINKS = {"mensual": MINIAPP_URL + "/membresia"}

PAYPAL_CLIENT_ID     = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID    = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_MODE          = os.getenv("PAYPAL_MODE", "live")
PAYPAL_BASE          = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"

PAYPAL_PRECIOS = {
    "copper":   "3.00",
    "silver":   "4.50",
    "gold":     "11.49",
    "platinum": "22.00",
    "diamond":  "46.99",
}

PAYPAL_PLAN_IDS = {
    "copper":   os.getenv("PAYPAL_PLAN_ID_COPPER",   ""),
    "silver":   os.getenv("PAYPAL_PLAN_ID_SILVER",   ""),
    "gold":     os.getenv("PAYPAL_PLAN_ID_GOLD",     ""),
    "platinum": os.getenv("PAYPAL_PLAN_ID_PLATINUM", ""),
    "diamond":  os.getenv("PAYPAL_PLAN_ID_DIAMOND",  ""),
}

_paypal_token_cache = {"token": None, "expires_at": 0}

def paypal_get_token() -> str:
    import time as _time
    now = _time.time()
    if _paypal_token_cache["token"] and now < _paypal_token_cache["expires_at"] - 60:
        return _paypal_token_cache["token"]
    resp = requests.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    _paypal_token_cache["token"]      = data["access_token"]
    _paypal_token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _paypal_token_cache["token"]

def paypal_crear_orden(plan: str, telegram_id: int, email: str = "") -> dict:
    precio = PAYPAL_PRECIOS.get(plan)
    if not precio:
        raise ValueError(f"Plan desconocido: {plan}")
    token = paypal_get_token()
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://cineapp-bot.onrender.com")
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": f"{telegram_id}_{plan}",
            "custom_id":    f"{telegram_id}|{plan}",
            "description":  f"QuehayApp VIP — Plan {plan.upper()}",
            "amount": {"currency_code": "USD", "value": precio}
        }],
        "application_context": {
            "brand_name":          "QuehayApp VIP",
            "locale":              "en-US",
            "landing_page":        "LOGIN",
            "shipping_preference": "NO_SHIPPING",
            "user_action":         "PAY_NOW",
            "return_url": f"{render_url}/paypal/success",
            "cancel_url": f"{render_url}/paypal/cancel",
        }
    }
    resp = requests.post(
        f"{PAYPAL_BASE}/v2/checkout/orders",
        json=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "return=representation"},
        timeout=15
    )
    resp.raise_for_status()
    orden = resp.json()
    approve_link = next((l["href"] for l in orden.get("links", []) if l["rel"] == "payer-action"), None)
    return {"order_id": orden["id"], "approve_url": approve_link}

def paypal_capturar_orden(order_id: str) -> dict:
    token = paypal_get_token()
    resp = requests.post(
        f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()

def paypal_verificar_webhook(headers: dict, body_bytes: bytes) -> bool:
    if not PAYPAL_WEBHOOK_ID:
        return False
    token = paypal_get_token()
    verification_body = {
        "transmission_id":   headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "cert_url":          headers.get("PAYPAL-CERT-URL", ""),
        "auth_algo":         headers.get("PAYPAL-AUTH-ALGO", ""),
        "transmission_sig":  headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "webhook_id":        PAYPAL_WEBHOOK_ID,
        "webhook_event":     __import__("json").loads(body_bytes),
    }
    resp = requests.post(
        f"{PAYPAL_BASE}/v1/notifications/verify-webhook-signature",
        json=verification_body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=10
    )
    if resp.ok:
        result = resp.json().get("verification_status")
        return result == "SUCCESS"
    return False

def paypal_crear_suscripcion(plan: str, telegram_id: int, email: str = "") -> dict:
    plan_id = PAYPAL_PLAN_IDS.get(plan, "")
    if not plan_id:
        raise ValueError(
            f"No hay PAYPAL_PLAN_ID configurado para el plan '{plan}'. "
            f"Agrega la variable PAYPAL_PLAN_ID_{plan.upper()} en Render."
        )
    token = paypal_get_token()
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://cineapp-bot.onrender.com")
    body = {
        "plan_id":   plan_id,
        "custom_id": f"{telegram_id}|{plan}",
        "application_context": {
            "brand_name":          "QH Membership",
            "locale":              "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action":         "SUBSCRIBE_NOW",
            "return_url": f"{render_url}/paypal/success",
            "cancel_url": f"{render_url}/paypal/cancel",
        }
    }
    resp = requests.post(
        f"{PAYPAL_BASE}/v1/billing/subscriptions",
        json=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "return=representation"},
        timeout=15
    )
    resp.raise_for_status()
    sub = resp.json()
    approve_link = next((l["href"] for l in sub.get("links", []) if l["rel"] == "approve"), None)
    return {"subscription_id": sub.get("id"), "approve_url": approve_link, "status": sub.get("status")}

def paypal_cancelar_suscripcion(subscription_id: str, motivo: str = "Cancelado por el usuario") -> bool:
    try:
        token = paypal_get_token()
        resp  = requests.post(
            f"{PAYPAL_BASE}/v1/billing/subscriptions/{subscription_id}/cancel",
            json={"reason": motivo},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10
        )
        return resp.status_code == 204
    except Exception as e:
        print(f"⚠️ Error cancelando suscripción {subscription_id}: {e}")
        return False

def paypal_obtener_suscripcion(subscription_id: str) -> dict:
    token = paypal_get_token()
    resp  = requests.get(
        f"{PAYPAL_BASE}/v1/billing/subscriptions/{subscription_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()

GMAIL_USER      = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD  = os.getenv("GMAIL_PASSWORD", "")
GMAIL_FROM_NAME = "QuehayApp VIP"


# ============ TMDB HELPERS ============
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/w500"

TIPO_TMDB = {
    "pelicula": "movie",
    "serie":    "tv",
    "anime":    "tv",
}

def tmdb_get(path, params=None):
    from providers.tmdb import TMDBClient
    return TMDBClient(TMDB_API_KEY).get(path, params)

def importar_desde_tmdb(tmdb_id: int, tipo: str) -> dict:
    endpoint_tipo = TIPO_TMDB.get(tipo, "movie")
    data = tmdb_get(f"/{endpoint_tipo}/{tmdb_id}")
    titulo = data.get("title") or data.get("name") or "Sin título"
    fecha_raw = data.get("release_date") or data.get("first_air_date") or ""
    año = int(fecha_raw[:4]) if fecha_raw and len(fecha_raw) >= 4 else None
    generos_raw = data.get("genres", [])
    genero = ", ".join(g["name"] for g in generos_raw) if generos_raw else ""
    poster_path = data.get("poster_path") or ""
    imagen_url = f"{TMDB_IMG}{poster_path}" if poster_path else ""
    sinopsis = data.get("overview") or ""
    rating = round(data.get("vote_average", 0), 1)
    from providers.tmdb import trailer_url
    trailer = trailer_url(tmdb_get, endpoint_tipo, tmdb_id)
    return {
        "titulo":    titulo,
        "tipo":      tipo,
        "genero":    genero,
        "año":       año,
        "imagen_url": imagen_url,
        "sinopsis":  sinopsis,
        "rating":    rating,
        "tmdb_id":   tmdb_id,
        **({'trailer_url':trailer} if trailer else {}),
        "backdrop_url": f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}" if data.get('backdrop_path') else '',
        "disponible": True,
        "destacado": False,
    }

# ============ ENVÍO A CANALES ============

def generar_estrellas(rating: float) -> str:
    if not rating:
        return "☆☆☆☆☆"
    estrellas_llenas = round(rating / 2)
    estrellas_vacias = 5 - estrellas_llenas
    return "★" * estrellas_llenas + "☆" * estrellas_vacias

def construir_caption(item: dict) -> str:
    tipo_emoji = {"pelicula": "🎬", "serie": "📺", "anime": "⛩️"}.get(item.get("tipo"), "🎬")
    tipo_label = {"pelicula": "PELÍCULA", "serie": "SERIE", "anime": "ANIME"}.get(item.get("tipo"), "")
    rating    = item.get("rating") or 0
    estrellas = generar_estrellas(float(rating))
    rating_str = f"{rating:.1f}/10" if rating else "N/D"
    generos  = item.get("genero") or "Sin género"
    año      = item.get("año") or "—"
    titulo   = item.get("titulo") or "Sin título"
    sinopsis = item.get("sinopsis") or ""
    if len(sinopsis) > 200:
        sinopsis = sinopsis[:197] + "..."
    return (
        f"{tipo_emoji} *{titulo}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏷 *Tipo:* {tipo_label}\n"
        f"📅 *Año:* {año}\n"
        f"🎭 *Género:* {generos}\n"
        f"⭐ *Rating:* {estrellas} `{rating_str}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📝 {sinopsis}\n"
    )

def construir_botones_canal(item: dict) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    btn_miniapp = InlineKeyboardButton(
        "🎬 Ver en QueHay",
        url=f"https://t.me/{BOT_USERNAME}?start=contenido_{int(item['id'])}"
    )
    btn_membresia = InlineKeyboardButton(
        "🎟 Acceso mensual",
        url=f"https://t.me/{BOT_USERNAME}?start=planes"
    )
    markup.add(btn_miniapp, btn_membresia)
    return markup

def _enviar_a_un_canal(canal_id, caption, markup, imagen):
    try:
        if imagen:
            bot.send_photo(chat_id=canal_id, photo=imagen, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id=canal_id, text=caption, parse_mode="Markdown", reply_markup=markup)
        print(f"✅ Enviado a {canal_id}")
        return True
    except Exception as e:
        print(f"❌ Error enviando a {canal_id}: {e}")
        return False

def enviar_contenido_al_canal(item: dict):
    caption = construir_caption(item)
    markup  = construir_botones_canal(item)
    imagen  = item.get("imagen_url", "")
    ok_publico = _enviar_a_un_canal(CANAL_PUBLICO_ID, caption, markup, imagen)
    ok_privado = _enviar_a_un_canal(CANAL_PRIVADO_ID, caption, markup, imagen)
    return ok_publico or ok_privado

# ============ PROGRAMADOR AUTOMÁTICO 3x DÍA ============

def obtener_siguiente_contenido_a_publicar():
    ahora_lima = datetime.now(LIMA_TZ)
    print(f"DEBUG cron: ahora Lima={ahora_lima.strftime('%Y-%m-%d %H:%M')}")
    todos_publicados = supabase_service.table("publicaciones_canal").select("contenido_id").execute()
    ids_historicos = list({p["contenido_id"] for p in todos_publicados.data})
    print(f"DEBUG cron: publicados históricos: {len(ids_historicos)} ítems")
    total_res = supabase_service.table("contenido").select("id", count="exact").eq("disponible", True).execute()
    total_disponibles = total_res.count or 0
    if len(ids_historicos) >= total_disponibles and total_disponibles > 0:
        print(f"🔄 Catálogo completo publicado ({total_disponibles} ítems). Reiniciando ciclo...")
        supabase_service.table("publicaciones_canal").delete().neq("id", 0).execute()
        ids_historicos = []
    query = supabase_service.table("contenido").select("*").eq("disponible", True)
    for excluido_id in ids_historicos:
        query = query.neq("id", excluido_id)
    resultado = query.order("año", desc=True).order("id", desc=True).limit(1).execute()
    if resultado.data:
        print(f"DEBUG cron: siguiente a publicar: {resultado.data[0]['titulo']} (id={resultado.data[0]['id']})")
    else:
        print("DEBUG cron: sin contenido disponible")
    return resultado.data[0] if resultado.data else None

def registrar_publicacion(contenido_id: int):
    try:
        supabase_service.table("publicaciones_canal").insert({
            "contenido_id": contenido_id,
            "publicado_en": datetime.now(timezone.utc).isoformat()
        }).execute()
        print(f"✅ Publicación registrada para contenido_id={contenido_id}")
    except Exception as e:
        print(f"⚠️ Error registrando publicación: {e}")

# ============ FLASK APP ============
from marketing import marketing_bp, init_marketing, enviar_email as _enviar_email_mkt, _html_bienvenida as _html_bienvenida_mkt

app = Flask(__name__)

def legacy_access_expiry(telegram_id):
    if not telegram_id:
        return 0
    users = supabase_service.table("usuarios").select("id,membresia_activa,fecha_vencimiento").eq("telegram_id",telegram_id).execute().data
    if not users or not users[0].get("membresia_activa"):
        return 0
    def timestamp(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    try:
        user_end = timestamp(users[0]["fecha_vencimiento"])
        memberships = supabase_service.table("membresias_activas").select("fecha_fin").eq("usuario_id",users[0]["id"]).eq("estado","activa").execute().data
        return max([min(user_end, timestamp(row["fecha_fin"])) for row in memberships] or [0])
    except (ValueError, TypeError, KeyError):
        return 0


def acceso_vigente(telegram_id):
    identity = getattr(g, "identity", None) if has_request_context() else None
    account = identity["account"] if identity else (security_store.account(telegram_id=telegram_id) if telegram_id else None)
    if owner_access(account):
        return True
    if account and billing_store.expiry(account["id"]) > time.time():
        return True
    return legacy_access_expiry(telegram_id) > time.time()


def account_legacy_expiry(account_id):
    account = security_store.account(id=account_id)
    return legacy_access_expiry(account.get("telegram_id")) if account else 0

security_store = install_security(app, acceso_vigente)
from billing.store import BillingStore
from billing.config import PLAN
from routes.payments import payment_routes
billing_store = BillingStore(security_store)
app.register_blueprint(payment_routes(billing_store, security_store, account_legacy_expiry))
from routes.pwa import pwa_routes
app.register_blueprint(pwa_routes())
from providers.vimeus import VimeusClient, ImportFailure
from services.vimeus_import import ImportRepository, import_title
from routes.vimeus import create_vimeus_routes
if LOCAL_MODE:
    from services.local_vimeus import DemoVimeus
    vimeus_provider = DemoVimeus()
else:
    vimeus_provider = VimeusClient(os.getenv("VIMEUS_API_KEY", ""))
app.register_blueprint(create_vimeus_routes(supabase_service, vimeus_provider, tmdb_get if TMDB_API_KEY else None))
from routes.catalog_import import catalog_import_routes
app.register_blueprint(catalog_import_routes(supabase_service,vimeus_provider,tmdb_get if TMDB_API_KEY else None))

app.register_blueprint(marketing_bp)
from telegram_bot.assistant import QueHayBot


def publicar_desde_bot(item):
    ok = enviar_contenido_al_canal(item)
    if ok:
        registrar_publicacion(item["id"])
    return ok


telegram_assistant = QueHayBot(bot, supabase_service, security_store, billing_store,
    legacy_access_expiry, MINIAPP_URL, publicar_desde_bot).register()
init_marketing(supabase_service, bot, ADMIN_IDS, BOT_USERNAME,
               active_access=lambda tid: telegram_assistant.access(tid)['active'])

@app.route("/")
def serve_miniapp():
    response = send_from_directory("static", "index.html")
    if LOCAL_MODE:
        response.direct_passthrough = False
        html = response.get_data(as_text=True)
        if not app.config.get('TELEGRAM_PREVIEW'):
            html = html.replace('https://telegram.org/js/telegram-web-app.js', '/static/telegram-local.js')
        html = html.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', '')
        response.set_data(html)
    return response

@app.route("/admin")
def serve_admin():
    return send_from_directory("static", "admin.html")

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    return app.extensions["admin_login"]()

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
@app.route('/webhook/telegram', methods=['POST'])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ============ ENDPOINTS ============

@app.route("/aprobar_pago", methods=["POST"])
def aprobar_pago():
    return jsonify(error="El flujo anterior está retirado. Revisa los pagos en el panel de acceso mensual."), 410

@app.route("/crear_pago_tarjeta", methods=["POST"])
def crear_pago_tarjeta():
    return jsonify(error="Usa el nuevo acceso mensual en /membresia. El checkout anterior está retirado."), 409

@app.route("/crear_pedido", methods=["POST"])
def crear_pedido():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        titulo = data.get("titulo")
        tipo   = data.get("tipo")
        if not telegram_id or not titulo:
            return jsonify({"error": "Datos incompletos"}), 400
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
        if not usuario_res.data:
            return jsonify({"error": "Usuario no encontrado"}), 404
        usuario = usuario_res.data[0]
        if not usuario.get("membresia_activa"):
            return jsonify({"error": "No tienes membresía activa"}), 403
        hoy = datetime.now().isoformat()
        mem_res = supabase_service.table("membresias_activas").select("*") \
            .eq("usuario_id", usuario["id"]).eq("estado","activa").gte("fecha_fin",hoy).execute()
        if not mem_res.data:
            return jsonify({"error": "No hay membresía activa válida"}), 403
        membresia = mem_res.data[0]
        plan_res = supabase_service.table("membresias_planes").select("*").eq("id", membresia["plan_id"]).execute()
        if not plan_res.data:
            return jsonify({"error": "Plan no encontrado"}), 404
        plan = plan_res.data[0]
        pedidos_extra = membresia.get("pedidos_extra", 0)
        limite_total  = plan["pedidos_por_mes"] + pedidos_extra
        if limite_total == 0:
            return jsonify({"error": "Tu plan no incluye pedidos"}), 403
        usados_res = supabase_service.table("pedidos").select("*", count="exact") \
            .eq("usuario_id", telegram_id).gte("fecha_pedido", membresia["fecha_inicio"]).lte("fecha_pedido", hoy).execute()
        usados = usados_res.count if hasattr(usados_res, 'count') else len(usados_res.data)
        if usados >= limite_total:
            return jsonify({"error": "Has alcanzado el límite de tu plan"}), 403
        supabase_service.table("pedidos").insert({
            "usuario_id": telegram_id, "titulo_pedido": titulo,
            "tipo": tipo, "estado": "pendiente",
            "fecha_pedido": datetime.now().isoformat()
        }).execute()
        restantes = limite_total - (usados + 1)
        for _admin in ADMIN_IDS:
            try:
                bot.send_message(_admin,
                    f"📥 NUEVO PEDIDO\n👤 Usuario: {telegram_id}\n🎬 Título: {titulo}\n📦 Plan: {plan['nombre']}\n📊 Restantes: {restantes}")
            except Exception as e_admin:
                print(f"⚠️ No se pudo notificar al admin {_admin}: {e_admin}")
        bot.send_message(telegram_id,
            f"✅ Pedido enviado correctamente.\n📦 Te quedan {restantes} pedidos disponibles.")
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin_pedidos", methods=["POST", "OPTIONS"])
def admin_pedidos():
    if request.method == "OPTIONS":
        r = jsonify({"success": True})
        r.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "POST"})
        return r, 200
    data = request.get_json()
    if not check_admin(data):
        return jsonify({"error": "No autorizado"}), 403
    pedidos_res = supabase_service.table("pedidos").select("*, usuarios!inner(*)").order("fecha_pedido", desc=True).execute()
    pedidos = [{
        "id": p["id"], "pedido_id": p["id"],
        "titulo": p["titulo_pedido"], "tipo": p.get("tipo","pelicula"),
        "estado": p["estado"],
        "fecha": datetime.fromisoformat(p["fecha_pedido"]).strftime("%d/%m/%Y %H:%M"),
        "usuario": {"telegram_id": p["usuarios"]["telegram_id"],
                    "nombre": p["usuarios"].get("nombre","Desconocido"),
                    "membresia": p["usuarios"].get("membresia_tipo","Ninguna")}
    } for p in pedidos_res.data]
    r = jsonify({"pedidos": pedidos, "total": len(pedidos),
                 "pendientes": len([p for p in pedidos if p["estado"] == "pendiente"])})
    r.headers.add("Access-Control-Allow-Origin","*")
    return r, 200

@app.route("/marcar_entregado", methods=["POST", "OPTIONS"])
def marcar_entregado():
    if request.method == "OPTIONS":
        r = jsonify({"success": True})
        r.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "POST"})
        return r, 200
    data = request.get_json()
    if not check_admin(data):
        return jsonify({"error": "No autorizado"}), 403

    pedido_id    = data.get("pedido_id")
    nuevo_estado = data.get("estado", "entregado")

    estados_validos = ("recibido", "en_proceso", "entregado")
    if nuevo_estado not in estados_validos:
        return jsonify({"error": f"Estado inválido. Usa: {', '.join(estados_validos)}"}), 400

    pedido_res = supabase_service.table("pedidos").select("*, usuarios!inner(*)").eq("id", pedido_id).execute()
    if not pedido_res.data:
        return jsonify({"error": "Pedido no encontrado"}), 404
    pedido = pedido_res.data[0]

    update_data = {"estado": nuevo_estado}
    if nuevo_estado == "entregado":
        update_data["fecha_respuesta"] = datetime.now().isoformat()

    supabase_service.table("pedidos").update(update_data).eq("id", pedido_id).execute()

    titulo = pedido.get("titulo_pedido", "tu pedido")
    mensajes = {
        "recibido":   f"👀 *Pedido recibido*\n\nHemos recibido tu solicitud de *{titulo}*.\nEstamos revisándola, te avisamos pronto.",
        "en_proceso": f"⚙️ *En proceso*\n\nEstamos trabajando en *{titulo}*.\nCasi listo, te notificamos cuando esté disponible.",
        "entregado":  f"✅ *¡Ya está disponible!*\n\n*{titulo}* ya está en los canales.\nAbre la Mini App para verlo.",
    }
    try:
        bot.send_message(
            pedido["usuarios"]["telegram_id"],
            mensajes[nuevo_estado],
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ No se pudo notificar al usuario: {e}")

    r = jsonify({"success": True, "estado": nuevo_estado})
    r.headers.add("Access-Control-Allow-Origin", "*")
    return r, 200

@app.route("/mis_pedidos", methods=["POST", "OPTIONS"])
def mis_pedidos():
    if request.method == "OPTIONS":
        r = jsonify({"success": True})
        r.headers.update({"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type","Access-Control-Allow-Methods":"POST"})
        return r, 200
    data = request.get_json()
    telegram_id = data.get("telegram_id")
    if not telegram_id:
        return jsonify({"error": "telegram_id requerido"}), 400
    pedidos_res = supabase_service.table("pedidos").select("*").eq("usuario_id", telegram_id).order("fecha_pedido", desc=True).execute()
    pedidos = [{"id":p["id"],"titulo":p["titulo_pedido"],"tipo":p.get("tipo","pelicula"),
                "estado":p["estado"],"fecha":datetime.fromisoformat(p["fecha_pedido"]).strftime("%d/%m/%Y %H:%M")}
               for p in pedidos_res.data]
    usuario_res = supabase_service.table("usuarios").select("membresia_tipo,membresia_activa").eq("telegram_id",telegram_id).execute()
    r = jsonify({"pedidos": pedidos, "total": len(pedidos), "usuario": usuario_res.data[0] if usuario_res.data else None})
    r.headers.add("Access-Control-Allow-Origin","*")
    return r, 200

@app.route("/api/admin/importar_tmdb", methods=["POST"])
def api_importar_tmdb():
    try:
        data = request.get_json(force=True, silent=True) or {}
        try:
            admin_id = int(data.get("admin_id", 0))
        except (ValueError, TypeError):
            admin_id = 0
        try:
            tmdb_id = int(data.get("tmdb_id", 0))
        except (ValueError, TypeError):
            tmdb_id = 0
        tipo = str(data.get("tipo", "pelicula")).lower().strip()
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        if not tmdb_id:
            return jsonify({"error": "tmdb_id requerido o invalido"}), 400
        if tipo not in ("pelicula", "serie", "anime"):
            return jsonify({"error": f"tipo invalido: '{tipo}'. Debe ser: pelicula, serie o anime"}), 400
        if tipo in ("serie", "anime"):
            try:
                result = import_title(vimeus_provider, ImportRepository(supabase_service), tmdb_id, tipo, tmdb_get if TMDB_API_KEY else None)
                return jsonify(**result, id=result["contenido_id"], tipo=tipo)
            except ImportFailure as exc:
                return jsonify(error=str(exc)), 422
        if not TMDB_API_KEY:
            return jsonify({"error": "TMDB_API_KEY no configurada en el servidor"}), 500
        contenido = importar_desde_tmdb(int(tmdb_id), tipo)
        existe = supabase_service.table("contenido").select("id").eq("tmdb_id", int(tmdb_id)).eq("tipo", tipo).execute()
        if existe.data:
            return jsonify({"error": f"Ya existe: {contenido['titulo']}", "id": existe.data[0]["id"]}), 409
        resultado = supabase_service.table("contenido").insert(contenido).execute()
        nuevo_id  = resultado.data[0]["id"] if resultado.data else None
        return jsonify({
            "success": True, "id": nuevo_id,
            "titulo": contenido["titulo"], "tipo": contenido["tipo"],
            "año": contenido["año"], "genero": contenido["genero"],
            "rating": contenido["rating"], "imagen_url": contenido["imagen_url"],
        }), 200
    except requests.HTTPError as e:
        return jsonify({"error": f"TMDB error: {e.response.status_code}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/contenido", methods=["POST"])
def api_admin_contenido():
    data = request.get_json()
    if not check_admin(data):
        return jsonify({"error": "No autorizado"}), 403
    limit  = int(data.get("limit", 20))
    offset = int(data.get("offset", 0))
    tipo   = data.get("tipo", "todo")
    query  = supabase_service.table("contenido").select("*", count="exact")
    if tipo != "todo":
        query = query.eq("tipo", tipo)
    resultado = query.order("id", desc=True).range(offset, offset + limit - 1).execute()
    return jsonify({"data": resultado.data, "total": resultado.count}), 200

@app.route("/api/admin/publicar", methods=["POST"])
def api_admin_publicar():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        contenido_id = int(data.get("contenido_id", 0))
        if not contenido_id:
            return jsonify({"error": "contenido_id requerido"}), 400
        res = supabase_service.table("contenido").select("*").eq("id", contenido_id).execute()
        if not res.data:
            return jsonify({"error": f"Contenido {contenido_id} no encontrado"}), 404
        item = res.data[0]
        ok = enviar_contenido_al_canal(item)
        if ok:
            registrar_publicacion(contenido_id)
            return jsonify({"success": True, "titulo": item["titulo"]}), 200
        else:
            return jsonify({"error": "No se pudo enviar a ningún canal."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/importar_temporadas", methods=["POST"])
def api_importar_temporadas():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        contenido_id = int(data.get("contenido_id", 0))
        if not contenido_id:
            return jsonify({"error": "contenido_id requerido"}), 400
        contenido_res = supabase_service.table("contenido").select("*").eq("id", contenido_id).execute()
        if not contenido_res.data:
            return jsonify({"error": "Contenido no encontrado"}), 404
        contenido = contenido_res.data[0]
        if contenido.get("tipo") not in ("serie", "anime"):
            return jsonify({"error": "Solo se pueden importar temporadas de series o anime"}), 400
        tmdb_id = contenido.get("tmdb_id")
        if not tmdb_id:
            return jsonify({"error": "Este contenido no tiene tmdb_id."}), 400
        resultado = import_title(vimeus_provider, ImportRepository(supabase_service), tmdb_id, contenido["tipo"], tmdb_get if TMDB_API_KEY else None)
        return jsonify(**resultado, insertadas=resultado["temporadas"], omitidas=0), 200
    except ImportFailure as exc:
        return jsonify(error=str(exc)), 422
    except requests.HTTPError as e:
        return jsonify({"error": f"TMDB error {e.response.status_code}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/temporadas/<int:contenido_id>", methods=["GET"])
def api_get_temporadas(contenido_id):
    try:
        res = supabase_service.table("temporadas") \
            .select("*").eq("contenido_id", contenido_id).order("numero").execute()
        return jsonify({"temporadas": res.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/temporadas/enlace", methods=["POST"])
def api_actualizar_enlace_temporada():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        temporada_id = int(data.get("temporada_id", 0))
        enlace       = data.get("enlace", "").strip()
        if not temporada_id:
            return jsonify({"error": "temporada_id requerido"}), 400
        supabase_service.table("temporadas").update({"enlace": enlace or None}).eq("id", temporada_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/temporadas/delete", methods=["POST"])
def api_eliminar_temporada():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        temporada_id = int(data.get("temporada_id", 0))
        if not temporada_id:
            return jsonify({"error": "temporada_id requerido"}), 400
        supabase_service.table("temporadas").delete().eq("id", temporada_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# WEBHOOK PAYPAL
# ============================================================

@app.route("/webhook/paypal", methods=["POST"])
def webhook_paypal():
    if not paypal_verificar_webhook(request.headers, request.get_data()):
        return jsonify(error="Firma no válida."), 400
    return jsonify(error="PayPal y las suscripciones anteriores están retirados."), 410

@app.route("/paypal/success", methods=["GET"])
def paypal_success():
    return f"""<html><head><meta charset="utf-8">
    <meta http-equiv="refresh" content="3;url=https://t.me/{BOT_USERNAME}">
    <style>body{{font-family:Arial;background:#0d0d0f;color:#f0f0f2;display:flex;
    align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}}</style>
    </head><body><div>
    <div style="font-size:52px">🎉</div>
    <h2 style="color:#e8b04b">¡Pago completado!</h2>
    <p style="color:#aaa">Tu membresía se activará en segundos.<br>Redirigiendo al bot...</p>
    </div></body></html>""", 200

@app.route("/paypal/cancel", methods=["GET"])
def paypal_cancel():
    return f"""<html><head><meta charset="utf-8">
    <meta http-equiv="refresh" content="3;url=https://t.me/{BOT_USERNAME}">
    <style>body{{font-family:Arial;background:#0d0d0f;color:#f0f0f2;display:flex;
    align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}}</style>
    </head><body><div>
    <div style="font-size:52px">↩️</div>
    <h2 style="color:#aaa">Pago cancelado</h2>
    <p style="color:#666">No se realizó ningún cargo. Regresando al bot...</p>
    </div></body></html>""", 200

@app.route("/api/admin/marketing/crear_pago_paypal", methods=["POST"])
def api_crear_pago_paypal():
    return jsonify(error="PayPal y las suscripciones automáticas ya no se ofrecen."), 410

@app.route("/cron/publicar_contenido", methods=["GET"])
def cron_publicar_contenido():
    try:
        item = obtener_siguiente_contenido_a_publicar()
        if not item:
            return jsonify({"message": "Sin contenido disponible"}), 200
        ok = enviar_contenido_al_canal(item)
        if ok:
            registrar_publicacion(item["id"])
            return jsonify({"success": True, "titulo": item["titulo"]}), 200
        else:
            return jsonify({"error": "No se pudo enviar a ningún canal."}), 500
    except Exception as e:
        tb = traceback.format_exc()
        print(f"❌ Error en cron publicar: {e}\n{tb}")
        return jsonify({"error": str(e), "traceback": tb}), 500

@app.route("/cron/verificar_vencimientos", methods=["GET"])
def cron_verificar_vencimientos():
    try:
        verificar_vencimientos()
        if os.getenv('CATALOG_IMPORT_ENABLED') == 'true' and not LOCAL_MODE and not catalog_job_store.get_setting('paused'):
            from services.catalog_jobs import run_production_batch
            return jsonify(run_production_batch(catalog_job_store, supabase_service,
                           os.getenv('VIMEUS_API_KEY', ''), os.getenv('TMDB_API_KEY', '')))
        return "OK", 200
    except Exception as e:
        return "Error", 500

def verificar_vencimientos():
    # Access is checked against expiry on every playback/download request.
    # The old channel ban/reminder cron must not mutate memberships or contact users.
    return {"access_enforced": True, "legacy_channel_actions": False}


from services.catalog_jobs import DurableQueue
catalog_job_store = DurableQueue(security_store)


@app.get('/api/admin/catalog/queue')
def catalog_queue_status():
    configured=os.getenv('CATALOG_IMPORT_ENABLED') == 'true' and not LOCAL_MODE
    return jsonify(enabled=configured and not bool(catalog_job_store.get_setting('paused')), configured=configured,
                   queue=catalog_job_store.summary())


@app.post('/api/admin/catalog/queue/settings')
def catalog_queue_settings():
    enabled=request.json.get('enabled')
    if type(enabled) is not bool:return jsonify(error='Elige activar o pausar.'),400
    catalog_job_store.set_setting('paused', 0 if enabled else 1)
    return catalog_queue_status()


@app.route("/api/usuario", methods=["POST"])
def api_usuario():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        if not telegram_id:
            return jsonify({"error": "telegram_id requerido"}), 400
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
        usuario = usuario_res.data[0] if usuario_res.data else None
        membresia = None
        if usuario:
            hoy = datetime.now().isoformat()
            mem_res = supabase_service.table("membresias_activas").select("*") \
                .eq("usuario_id", usuario["id"]).eq("estado","activa").gte("fecha_fin", hoy).execute()
            if mem_res.data:
                membresia = mem_res.data[0]
                plan_res = supabase_service.table("membresias_planes").select("*").eq("id", membresia["plan_id"]).execute()
                if plan_res.data:
                    membresia["membresias_planes"] = plan_res.data[0]
        return jsonify({"usuario": usuario, "membresia": membresia}), 200
    except Exception as e:
        return jsonify({"error": "Error interno"}), 500

@app.route("/api/planes", methods=["GET"])
def api_planes():
    return jsonify([PLAN])

@app.route("/api/contenido", methods=["POST"])
def api_contenido():
    data     = request.get_json()
    busqueda = data.get("busqueda","")
    tipo     = data.get("tipo","todo")
    try:
        limit = max(1, min(100, int(data.get("limit",20))))
        offset = max(0, min(100000, int(data.get("offset",0))))
    except (ValueError, TypeError):
        return jsonify(error="Paginación inválida."), 400
    query = supabase_service.table("contenido").select("*", count="exact").eq("disponible", True)
    alias=None
    if data.get("id") is not None:
        try:
            content_id=int(data['id'])
            from services.catalog_aliases import resolve_alias
            alias=resolve_alias(supabase_service,content_id)
            query = query.eq("id", alias['id'] if alias else content_id)
        except (ValueError, TypeError):
            return jsonify(error="ID inválido."), 400
    if tipo != "todo":
        query = query.eq("tipo", tipo)
    if busqueda:
        query = query.ilike("titulo", f"%{busqueda}%")
    genero = data.get("genero")
    if genero:
        query = query.ilike("genero", f"%{genero}%")
    year = data.get("año")
    if year not in (None, ""):
        try:
            if isinstance(year, bool) or not str(year).isdigit() or not 1888 <= int(year) <= datetime.now().year + 2:
                raise ValueError
            query = query.eq("año", int(year))
        except (TypeError, ValueError):
            return jsonify(error="Año inválido."), 400
    if data.get("descarga"):
        query = query.not_.is_("descarga","null").neq("descarga","")
    resultados = query.order("id", desc=True).range(offset, offset+limit-1).execute()
    if alias:resultados.data=[{**row,'start_season':alias['start_season']} for row in resultados.data]
    return jsonify({"data": resultados.data, "total": resultados.count})

@app.route("/api/admin/pagos", methods=["POST"])
def api_admin_pagos():
    data = request.get_json()
    if not check_admin(data):
        return jsonify({"error": "No autorizado"}), 403
    pagos = supabase_service.table("pagos_manuales").select("*") \
        .eq("estado","pendiente").order("created_at", desc=True).execute()
    return jsonify(pagos.data)

@app.route("/api/admin/usuarios", methods=["POST"])
def api_admin_usuarios():
    data = request.get_json()
    if not check_admin(data):
        return jsonify({"error": "No autorizado"}), 403
    usuarios = supabase_service.table("usuarios").select("*").order("id", desc=True).execute()
    return jsonify(usuarios.data)

@app.route("/api/mis_pedidos", methods=["POST"])
def api_mis_pedidos():
    data = request.get_json()
    telegram_id = data.get("telegram_id")
    if not telegram_id:
        return jsonify({"error": "telegram_id requerido"}), 400
    pedidos = supabase_service.table("pedidos").select("*").eq("usuario_id", telegram_id).order("fecha_pedido", desc=True).execute()
    pedidos_data = pedidos.data or []
    for p in pedidos_data:
        p["fecha"] = datetime.fromisoformat(p["fecha_pedido"].replace("Z","")).strftime("%d/%m/%Y %H:%M")
    return jsonify({"pedidos": pedidos_data, "usados": len(pedidos_data)})

@app.route("/api/config/vimeus_key", methods=["GET"])
def get_vimeus_key():
    return jsonify({"error": "Usa la reproducción autenticada por contenido."}), 410

def enlace_externo_seguro(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.hostname in ("localhost", "127.0.0.1", "::1") or "." not in parsed.hostname:
            return None
        return value
    except ValueError:
        return None

from routes.episode_downloads import episode_download_routes
app.register_blueprint(episode_download_routes(supabase_service, acceso_vigente, enlace_externo_seguro))
from routes.okru import okru_routes
app.register_blueprint(okru_routes(supabase_service))

from services.popularity import Popularity
from routes.popularity import popularity_routes
popularity_store = Popularity(security_store)
app.register_blueprint(popularity_routes(supabase_service, popularity_store))
from routes.profile import profile_routes
app.register_blueprint(profile_routes(supabase_service, security_store))

@app.route("/api/playback/<int:contenido_id>", methods=['GET','POST'])
def api_playback(contenido_id):
    result = supabase_service.table("contenido").select("*").eq("id", contenido_id).eq("disponible", True).execute()
    if not result.data:
        return jsonify(error="Contenido no disponible."), 404
    item = result.data[0]
    if item.get('fuente') == 'okru':
        from providers.okru import embed_url
        link = item.get('playback_url')
        if 'episodio_id' in request.args:
            episode_id=request.args.get('episodio_id',type=int)
            episodes=supabase_service.table('episodios').select('temporada_id,playback_url').eq('id',episode_id).eq('disponible',True).execute().data if episode_id else []
            seasons=supabase_service.table('temporadas').select('id').eq('id',episodes[0]['temporada_id']).eq('contenido_id',contenido_id).execute().data if episodes else []
            if not seasons:return jsonify(error='Este capítulo no pertenece al título o ya no está disponible.'),404
            link=episodes[0].get('playback_url')
        url=embed_url(link)
        if not url:return jsonify(error='Este vídeo todavía no está disponible.'),404
        if request.method=='POST' and not g.identity.get('admin'):
            try:popularity_store.record(g.identity['account']['id'],contenido_id)
            except Exception:app.logger.warning('Popularity recording unavailable')
        return jsonify(url=url,embed=True,provider='okru')
    if item.get("fuente") == "vimeus" and item.get("tmdb_id"):
        key = os.getenv("VIMEUS_VIEW_KEY", "")
        if not key:
            return jsonify(error="Reproductor pendiente de configuración."), 503
        kind = {"pelicula": "movie", "serie": "serie", "anime": "anime"}.get(item["tipo"])
        if not kind:
            return jsonify(error="Tipo no reproducible."), 400
        params = {"tmdb": item["tmdb_id"], "view_key": key}
        from providers.player_brand import quehay_player_params
        params.update(quehay_player_params(app.config['APP_ORIGIN']))
        if item["tipo"] in ("serie", "anime"):
            episode_id = request.args.get("episodio_id", type=int)
            if not episode_id:
                if 'episodio_id' in request.args:
                    return jsonify(error="Episodio inválido."), 400
                # Vimeus documents se/ep as optional: its own selector can be
                # used before a verified Listing snapshot has been imported.
                return jsonify(url="https://vimeus.com/e/"+kind+"?"+urlencode(params), embed=True, provider_selection=True)
            episodes = supabase_service.table("episodios").select("temporada_id,numero").eq("id", episode_id).eq("disponible", True).execute().data
            seasons = supabase_service.table("temporadas").select("numero").eq("id", episodes[0]["temporada_id"]).eq("contenido_id", contenido_id).execute().data if episodes else []
            if not seasons:
                return jsonify(error="Este capítulo no pertenece al título o ya no está disponible."), 404
            params.update(se=seasons[0]["numero"], ep=episodes[0]["numero"])
        if request.method == 'POST' and not g.identity.get('admin'):
            try:
                popularity_store.record(g.identity['account']['id'], contenido_id)
            except Exception:
                app.logger.warning('Popularity recording unavailable')
        return jsonify(url="https://vimeus.com/e/"+kind+"?"+urlencode(params), embed=True)
    link = item.get("enlace_canal")
    season_id = request.args.get("temporada_id", type=int)
    if season_id:
        seasons = supabase_service.table("temporadas").select("enlace").eq("id", season_id).eq("contenido_id", contenido_id).execute()
        if seasons.data:
            link = seasons.data[0].get("enlace") or link
    link = enlace_externo_seguro(link)
    return jsonify(url=link, embed=False) if link else (jsonify(error="Reproducción no disponible."), 404)

@app.get("/api/download/<int:contenido_id>")
def api_download(contenido_id):
    if not acceso_vigente(g.identity["account"].get("telegram_id")):
        return jsonify(error="Tu acceso no está activo o ha vencido.",code='membership_required'), 403
    result = supabase_service.table("contenido").select("descarga").eq("id", contenido_id).eq("disponible", True).execute()
    link = enlace_externo_seguro(result.data[0].get("descarga")) if result.data else None
    if not link:
        return jsonify(error="Este contenido no tiene un enlace de descarga válido."), 404
    return jsonify(url=link, host=urlsplit(link).hostname)

@app.route("/api/tendencias", methods=["GET"])
def api_tendencias():
    resultados = supabase_service.table("contenido").select("*") \
        .eq("destacado", True).eq("disponible", True).order("orden_destacado").limit(10).execute()
    return jsonify(resultados.data)

@app.route("/webhook/buymeacoffee", methods=["POST"])
def webhook_buymeacoffee():
    from billing.webhook import process_bmc
    result, status = process_bmc(request.get_data(), request.headers.get("x-signature-sha256", ""), billing_store, account_legacy_expiry)
    return jsonify(result), status

# ============ INICIO ============

if __name__ == "__main__":
    raise RuntimeError("Usa scripts/run_local.py en local o gunicorn main:app en producción. No se registran webhooks automáticamente.")
