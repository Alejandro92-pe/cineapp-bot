from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
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

# ============ VARIABLES DE ENTORNO ============
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ADMIN_ID ahora acepta uno o varios IDs separados por coma, ej:
# ADMIN_ID=123456789,987654321
_admin_id_raw = os.getenv("ADMIN_ID", "0")
ADMIN_IDS = {int(x.strip()) for x in _admin_id_raw.split(",") if x.strip()}
# Se mantiene ADMIN_ID (un solo valor) para el código que lo usa como
# "admin principal" al registrar quién hizo una activación, etc.
ADMIN_ID = next(iter(ADMIN_IDS), 0)

SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def check_admin(data):
    """Verifica admin_id tolerando int y string."""
    try:
        return int(data.get("admin_id", 0)) in ADMIN_IDS
    except (ValueError, TypeError):
        return False

def is_admin(user_id):
    """Verifica si un user_id de Telegram es alguno de los admins."""
    try:
        return int(user_id) in ADMIN_IDS
    except (ValueError, TypeError):
        return False

# Contraseña del panel admin (static/admin.html), validada en backend.
# Config esto en Render como variable de entorno ADMIN_PASSWORD.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

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

CANALES_VIP = [CANAL_PELICULAS_ID, CANAL_SERIES_ID, GRUPO_CONTENIDO_ID] + ([CANAL_ANIME_ID] if CANAL_ANIME_ID else [])

def desbanear_usuario(user_id: int):
    """
    Elimina al usuario de la lista de expulsados en todos los canales VIP.
    SIEMPRE debe llamarse antes de enviar enlaces de acceso.
    Si el usuario no estaba baneado, unban_chat_member lo ignora silenciosamente.
    """
    errores = []
    for canal in CANALES_VIP:
        try:
            bot.unban_chat_member(chat_id=canal, user_id=user_id, only_if_banned=True)
            print(f"✅ Unban {user_id} en {canal}")
        except Exception as e:
            errores.append(f"{canal}: {e}")
            print(f"⚠️ Unban fallido {user_id} en {canal}: {e}")
    return len(errores) == 0

MINIAPP_URL = "https://cineapp-bot.onrender.com"
BMC_URL     = "https://buymeacoffee.com/quehay/extras"
BMC_LINKS   = {
    "copper":   "https://buymeacoffee.com/quehay/e/517243",
    "silver":   "https://buymeacoffee.com/quehay/e/517244",
    "gold":     "https://buymeacoffee.com/quehay/e/510546",
    "platinum": "https://buymeacoffee.com/quehay/e/510549",
    "diamond":  "https://buymeacoffee.com/quehay/e/510552",
}

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
        print("⚠️ PAYPAL_WEBHOOK_ID no configurado — omitiendo verificación")
        return True
    token = paypal_get_token()
    verification_body = {
        "transmission_id":   headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "cert_url":          headers.get("PAYPAL-CERT-URL", ""),
        "auth_algo":         headers.get("PAYPAL-AUTH-ALGO", ""),
        "transmission_sig":  headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "webhook_id":        PAYPAL_WEBHOOK_ID,
        "webhook_event":     body_bytes.decode("utf-8"),
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

user_states = {}

# ============ TMDB HELPERS ============
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/w500"

TIPO_TMDB = {
    "pelicula": "movie",
    "serie":    "tv",
    "anime":    "tv",
}

def tmdb_get(path, params=None):
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    params["language"] = "es-MX"
    r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

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
    return {
        "titulo":    titulo,
        "tipo":      tipo,
        "genero":    genero,
        "año":       año,
        "imagen_url": imagen_url,
        "sinopsis":  sinopsis,
        "rating":    rating,
        "tmdb_id":   tmdb_id,
        "disponible": True,
        "destacado": False,
    }

def importar_temporadas_desde_tmdb(tmdb_id: int, contenido_id: int) -> dict:
    data = tmdb_get(f"/tv/{tmdb_id}")
    seasons_raw = data.get("seasons", [])
    seasons = [s for s in seasons_raw if s.get("season_number", 0) > 0]
    existentes_res = supabase_service.table("temporadas") \
        .select("numero").eq("contenido_id", contenido_id).execute()
    existentes = {e["numero"] for e in existentes_res.data}
    insertadas, omitidas = [], []
    for s in seasons:
        num = s.get("season_number")
        if num in existentes:
            omitidas.append(num); continue
        poster = s.get("poster_path") or data.get("poster_path") or ""
        supabase_service.table("temporadas").insert({
            "contenido_id": contenido_id,
            "numero":       num,
            "nombre":       s.get("name") or f"Temporada {num}",
            "poster_url":   f"{TMDB_IMG}{poster}" if poster else "",
            "descripcion":  s.get("overview") or "",
            "episodios":    s.get("episode_count") or 0,
            "enlace":       None,
        }).execute()
        insertadas.append(num)
    return {"insertadas": len(insertadas), "omitidas": len(omitidas), "numeros": insertadas}

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
        "🎬 Ver en Mini App",
        url=f"https://t.me/{BOT_USERNAME}?start=miniapp"
    )
    btn_membresia = InlineKeyboardButton(
        "💎 Obtener Membresía VIP",
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

# ============================================================
# FIX NOTIFICACIONES — nombres de columna corregidos
# Las columnas reales en Supabase son:
#   notificacion_3dias_enviada (boolean)
#   notificacion_3hora         (boolean)
#   notificacion_vencida_enviada (boolean)
# ============================================================

def _marcar_notif(usuario_id: int, campo: str):
    """
    Marca una notificación como enviada (True) en la tabla usuarios.
    FIX: nombres de columna corregidos para que coincidan con Supabase.
    """
    try:
        supabase_service.table("usuarios").update({
            campo: True   # ← boolean True, no timestamp
        }).eq("id", usuario_id).execute()
        print(f"✅ Notificación '{campo}' marcada para usuario {usuario_id}")
    except Exception as e:
        print(f"⚠️ Error marcando notificación {campo} para usuario {usuario_id}: {e}")

def _resetear_notifs(usuario_id: int):
    """
    Al renovar/activar membresía resetea los flags a False para el nuevo período.
    FIX: nombres de columna corregidos para que coincidan con Supabase.
    """
    try:
        supabase_service.table("usuarios").update({
            "notificacion_3dias_enviada":  False,   # ← nombre real en Supabase
            "notificacion_3horas_enviada":  False,   # ← nombre real en Supabase
            "notificacion_vencida_enviada": False,  # ← nombre real en Supabase
        }).eq("id", usuario_id).execute()
        print(f"✅ Flags de notificación reseteados para usuario {usuario_id}")
    except Exception as e:
        print(f"⚠️ Error reseteando flags para usuario {usuario_id}: {e}")

# ============ MENÚ PRINCIPAL ============

def menu_principal(chat_id, user_name=""):
    texto = (
        f"🎬 *¡Bienvenido {user_name} a QuehayApp VIP!*\n\n"
        "👇 *Selecciona una opción:*"
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💎 Ver Planes", "🎬 Beneficios VIP")
    markup.row("⭐ Testimonios", "💰 Cómo pagar")
    markup.row("📱 Mini App Vip", "🆘 Ayuda")
    bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

# ============ /start ============

@bot.message_handler(commands=['start'])
def start(message):
    user_id   = message.from_user.id
    user_name = message.from_user.first_name
    chat_id   = message.chat.id

    usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
    if not usuario.data:
        supabase_service.table('usuarios').insert({
            "telegram_id": user_id,
            "nombre": user_name,
            "membresia_activa": False
        }).execute()

    args = message.text.split()

    if len(args) > 1 and args[1].startswith("pago_"):
        partes = args[1].split("_")
        if len(partes) == 3:
            plan   = partes[1]
            precio = partes[2]
            supabase_service.table('pagos_manuales').insert({
                "usuario_id": user_id,
                "membresia_comprada": plan,
                "monto": precio,
                "metodo": "yape",
                "fecha_pago": datetime.now().isoformat(),
                "estado": "pendiente",
                "activado": False
            }).execute()
            user_states[user_id] = {"estado": "esperando_voucher", "plan": plan}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancelar pago", callback_data="cancelar_voucher"))
            bot.send_message(
                chat_id,
                f"💎 *PLAN {plan.upper()}*\n\n"
                f"💰 Monto a Pagar: S/{precio}\n\n"
                "📲 *Yape/Plin:* `930202820` (Richard Quiroz)\n"
                f"📝 Concepto: {user_id}\n\n"
                "📸 Envía la captura del voucher aquí\n"
                "🟢 Después de validar, tu membresía se activará.",
                parse_mode="Markdown",
                reply_markup=markup
            )
            return

    if len(args) > 1 and args[1] == "miniapp":
        texto = (
            "📱 *MINI APP VIP*\n\n"
            "Explora todo nuestro contenido:\n"
            "🎬 Películas • 📺 Series • ⛩️ Anime\n\n"
            "👇 Presiona el botón para abrir la Mini App:"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "🎬 Abrir Mini App",
            web_app=telebot.types.WebAppInfo(url=MINIAPP_URL)
        ))
        bot.send_message(chat_id, texto, parse_mode="Markdown", reply_markup=markup)
        return

    if len(args) > 1 and args[1] == "planes":
        texto = (
            "💎 *PLANES CON 50% OFF* 💎\n\n"
            "🥉 Copper • 🥈 Silver • 🥇 Gold • 🏆 Platinum • 💠 Diamond\n\n"
            "👇 Presiona el botón para ver los planes y comprar desde la Mini App:"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "💎 Ver Membresías",
            web_app=telebot.types.WebAppInfo(url=f"{MINIAPP_URL}?seccion=membresias")
        ))
        bot.send_message(chat_id, texto, parse_mode="Markdown", reply_markup=markup)
        return

    menu_principal(chat_id, user_name)

# ============ BOTONES DEL MENÚ ============

@bot.message_handler(func=lambda m: m.text == "💎 Ver Planes")
def ver_planes(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["planes"], parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎬 Beneficios VIP")
def beneficios(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["beneficios"], parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📱 Mini App Vip")
def miniapp_info(message):
    texto = (
        "📱 *¿QUÉ ES LA MINI APP VIP?*\n\n"
        "Es una aplicación dentro de Telegram donde puedes:\n\n"
        "🎬 Ver el catálogo completo de películas y series\n"
        "🔎 Buscar contenido fácilmente\n"
        "📦 Hacer pedidos según tu plan\n"
        "👤 Ver tu membresía y fecha de vencimiento\n"
        "💳 Comprar tu plan de forma segura\n\n"
        "🚀 Todo sin salir de Telegram.\n\n"
        "👇 Presiona el botón para abrir la app:"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "🎬 Abrir Mini App",
        web_app=telebot.types.WebAppInfo(url=MINIAPP_URL)
    ))
    bot.send_message(message.chat.id, texto, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Cómo pagar")
def como_pagar(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Ver cómo pagar con Yape / Plin",
            url="https://player.vimeo.com/video/1180635702"),
        InlineKeyboardButton("💳 Ver cómo pagar con Tarjeta",
            url="https://player.vimeo.com/video/1180635496")
    )
    bot.send_message(
        message.chat.id,
        "💰 <b>¿Cómo pagar tu membresía?</b>\n\n"
        "🎥 Mira estos tutoriales rápidos:\n\n"
        "👇 Elige tu método de pago",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Testimonios")
def testimonios(message):
    bot.send_message(message.chat.id,
        "⭐ *LO QUE DICEN NUESTROS MIEMBROS VIP*\n\n"
        "💬 'El mejor canal que encontré, siempre actualizan contenido.'\n\n"
        "💬 'Me encanta poder pedir películas y que las suban rápido.'\n\n"
        "💬 'Vale totalmente la pena, todo ordenado.'\n\n"
        "💎 ¿Te gustaría formar parte?\n"
        "Escribe *ver planes* para comenzar.",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "🆘 Ayuda")
def ayuda(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["ayuda"], parse_mode="Markdown")

# ============ CALLBACKS ============

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data    = call.data
    bot.answer_callback_query(call.id)

    if data == "pago_soles_general":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 Abrir Mini App",
            web_app=telebot.types.WebAppInfo(url=MINIAPP_URL)))
        bot.send_message(chat_id, "🇵🇪 Paga en soles desde la Mini App:", reply_markup=markup)

    elif data == "pago_dolares_general":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Pagar ahora", url=BMC_URL))
        bot.send_message(chat_id, "💳 Paga en dólares con tarjeta:", reply_markup=markup)

    elif data.startswith("plan_"):
        partes = data.split("_")
        if len(partes) >= 3:
            plan   = partes[1]
            moneda = partes[2]
            if moneda == "soles":
                user_states[user_id] = {"estado": "esperando_voucher", "plan": plan}
                bot.send_message(chat_id, f"📸 Envía el voucher del plan *{plan.upper()}*.", parse_mode="Markdown")
            elif moneda == "dolares":
                link = BMC_LINKS.get(plan)
                if link:
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("💳 Pagar ahora", url=f"{link}?ref={user_id}"))
                    bot.send_message(chat_id, f"💳 Has elegido *{plan.upper()}* en dólares.",
                        reply_markup=markup, parse_mode="Markdown")

    elif data == "cancelar_voucher":
        if user_id in user_states:
            del user_states[user_id]
            supabase_service.table('pagos_manuales') \
                .update({"estado": "cancelado"}) \
                .eq("usuario_id", user_id).eq("estado", "pendiente").execute()
            bot.send_message(chat_id, "✅ Pago cancelado.")
    else:
        bot.send_message(chat_id, "⚠️ Opción no reconocida.")

# ============ FOTOS (Voucher) ============

@bot.message_handler(content_types=['photo'])
def recibir_foto(message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    if user_id in user_states and user_states[user_id]["estado"] == "esperando_voucher":
        plan = user_states[user_id]["plan"]
        bot.send_message(chat_id,
            f"✅ ¡Voucher recibido! Tu pago de *{plan.upper()}* será revisado.",
            parse_mode="Markdown"
        )
        bot.send_photo(GRUPO_SOPORTE_ID, message.photo[-1].file_id,
            caption=f"📸 VOUCHER\nUsuario: {user_id}\nPlan: {plan.upper()}")
        del user_states[user_id]
        return
    fwd = bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    if fwd: _guardar_fwd(fwd.message_id, user_id)
    bot.send_message(chat_id, "📩 Tu imagen fue enviada a soporte.")

# ============ ARCHIVOS ============

@bot.message_handler(content_types=['video', 'document', 'audio', 'voice'])
def soporte_archivos(message):
    if message.chat.type != 'private':
        return
    if message.from_user.id in user_states:
        return
    fwd = bot.forward_message(GRUPO_SOPORTE_ID, message.chat.id, message.message_id)
    if fwd: _guardar_fwd(fwd.message_id, message.from_user.id)
    bot.send_message(message.chat.id, "📩 Tu archivo fue enviado a soporte.")

# ============ RESPUESTA DESDE GRUPO SOPORTE ============

_fwd_map = {}

def _guardar_fwd(fwd_msg_id, user_id):
    _fwd_map[fwd_msg_id] = user_id
    if len(_fwd_map) > 300:
        for k in list(_fwd_map.keys())[:100]: _fwd_map.pop(k, None)

def _uid_desde_reply(message):
    origen = message.reply_to_message
    if not origen: return None
    if origen.forward_from:
        return origen.forward_from.id
    uid = _fwd_map.get(origen.message_id)
    if uid: return uid
    texto = origen.caption or origen.text or ""
    m = re.search(r'Usuario[:\s]+(\d{5,})', texto)
    if m: return int(m.group(1))
    return None

@bot.message_handler(
    content_types=["text", "photo", "video", "document", "audio", "voice", "sticker"],
    func=lambda m: m.chat.id == GRUPO_SOPORTE_ID and m.reply_to_message is not None
)
def responder_desde_grupo(message):
    try:
        uid = _uid_desde_reply(message)
        if not uid:
            bot.reply_to(message,
                "❌ No se puede identificar al usuario (privacidad activada).\n"
                "Usa: /reply ID_USUARIO tu mensaje")
            return
        if message.text:
            bot.send_message(uid, f"📝 *Respuesta de soporte:*\n\n{message.text}", parse_mode="Markdown")
        elif message.photo:
            bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
        elif message.document:
            bot.send_document(uid, message.document.file_id, caption=message.caption or "")
        elif message.video:
            bot.send_video(uid, message.video.file_id, caption=message.caption or "")
        elif message.audio:
            bot.send_audio(uid, message.audio.file_id)
        elif message.voice:
            bot.send_voice(uid, message.voice.file_id)
        elif message.sticker:
            bot.send_sticker(uid, message.sticker.file_id)
        bot.reply_to(message, f"✅ Enviado al usuario {uid}.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ============ TEXTO LIBRE ============

@bot.message_handler(content_types=['text'])
def manejar_texto(message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_original = message.text.strip()
    text = text_original.lower()

    botones = ["💎 Ver Planes", "🎬 Beneficios VIP", "⭐ Testimonios",
               "🎞 Pedir Película", "📱 Mini App Vip", "🆘 Ayuda"]
    if text_original.startswith("/") or text_original in botones:
        return

    if user_id in user_states and user_states[user_id]["estado"] == "esperando_voucher":
        bot.send_message(chat_id, "❌ Envía una FOTO del voucher o presiona Cancelar.")
        return

    if any(p in text for p in ["humano", "admin", "persona", "real"]):
        bot.send_message(chat_id,
            "👨‍💼 Claro, te pondré en contacto con un administrador.\n"
            "📩 Tu mensaje fue enviado directamente al equipo.\n"
            "🕒 Te responderemos lo antes posible.")
        bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
        return

    for keyword in sorted(KEYWORD_REPLIES.keys(), key=len, reverse=True):
        if keyword in text:
            bot.send_message(chat_id, KEYWORD_REPLIES[keyword], parse_mode="Markdown")
            return

    fwd = bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    if fwd: _guardar_fwd(fwd.message_id, user_id)
    bot.send_message(chat_id, "📩 Tu mensaje fue enviado a soporte.")

# ============ KEYWORD REPLIES ============

KEYWORD_REPLIES = {
    "quiero comprar": "🛒 ¡Perfecto! ¿Qué plan deseas activar? Silver, Gold, Platinum o Diamond.\n\nPuedes pagar en *soles* (Yape/Plin) o en *dólares* (tarjeta automática).",
    "quiero el plan": "🛒 ¡Genial! ¿Qué plan deseas activar? Silver, Gold, Platinum o Diamond.",
    "como compro":    "🛒 Para activar tu membresía escribe 'planes' o abre la MiniApp.",
    "como comprar":   "🛒 Para activar tu membresía escribe 'planes' o abre la MiniApp.",
    "comprar": (
        "🛒 *¡Genial! Elige tu método de pago:*\n\n"
        "🇵🇪 *Yape/Plin* (pago en soles)\n"
        "💳 *Tarjeta internacional* (dólares, activación automática)\n\n"
        "¿Cuál prefieres?"
    ),
    "silver":   "🥈 *SILVER* incluye 2 pedidos por mes.\n\n¿Quieres pagar en *soles* o en *dólares*?",
    "gold":     "🥇 *GOLD* incluye 3 pedidos cada 3 meses.\n\n¿Quieres pagar en *soles* o en *dólares*?",
    "platinum": "🏆 *PLATINUM* incluye 5 pedidos cada 6 meses.\n\n¿Quieres pagar en *soles* o en *dólares*?",
    "diamond":  "💠 *DIAMOND* incluye 8 pedidos al año.\n\n¿Quieres pagar en *soles* o en *dólares*?",
    "copper":   "🥉 *COPPER* incluye acceso a canales sin pedidos.\n\n¿Quieres pagar en *soles* o en *dólares*?",
    "como pago": "💳 Puedes pagar en soles con Yape/Plin o en dólares con tarjeta automática.",
    "soles":    "🇵🇪 Para pagar en soles usa Yape o Plin desde la MiniApp.",
    "dólares":  "💳 Para pagar en dólares usa tarjeta (Buy Me a Coffee). Activación automática.",
    "yape":     "🇵🇪 Usa la MiniApp → Membresías → Selecciona tu plan → Yape/Plin → Envía voucher.",
    "plin":     "🇵🇪 El proceso es igual que Yape desde la MiniApp.",
    "tarjeta":  "💳 Pago con tarjeta es automático. Solo asegúrate de escribir tu email correctamente.",
    "ya pagué": "📩 Si ya enviaste tu voucher, no es necesario enviarlo nuevamente. Será verificado manualmente.",
    "ya pague": "📩 Si ya enviaste tu voucher, no es necesario enviarlo nuevamente. Será verificado manualmente.",
    "cuanto demora": "⏳ Pagos con tarjeta son automáticos. Pagos por Yape/Plin se verifican manualmente.",
    "no me activan": "🔍 Los pagos por Yape/Plin se revisan manualmente. Si pagaste de madrugada se activará desde las 7:00 AM.",
    "es seguro":  "🔐 Sí. Todos los pagos se verifican manualmente antes de activar membresías.",
    "es estafa":  "🔒 No realizamos estafas. Todos los pagos se validan manualmente antes de activar acceso.",
    "miniapp":    "📱 La MiniApp está dentro del bot, en la parte inferior izquierda.",
    "enlace":     "🔗 Si tienes membresía activa, los enlaces se enviaron automáticamente al activarse.",
    "pedido":     "📦 Para pedir películas necesitas membresía Silver o superior. Hazlo desde la MiniApp → Pedidos.",
    "beneficios": (
        "✨ *BENEFICIOS VIP* ✨\n\n"
        "🔐 Acceso privado\n"
        "📥 Descargas directas en Drive desde la Mini App\n"
        "🚫 Sin publicidad en Telegram web y Desktop\n"
        "🎞 Contenido exclusivo\n"
        "📦 Pedidos según plan\n"
        "🤖 Bot asistente\n\n"
        "Escribe 'planes' para ver membresías."
    ),
    "ayuda":   "🆘 Describe tu problema y soporte te responderá lo antes posible.",
    "soporte": "📞 Indica tu ID de Telegram y el detalle del problema para ayudarte.",
    "planes": (
        "💎 *PLANES DISPONIBLES — 50% OFF POR TIEMPO LIMITADO* 💎\n\n"
        "🥉 COPPER   : Antes: S/22 - $6   | Ahora: S/11 - $3\n"
        "🥈 SILVER   : Antes: S/33 - $9   | Ahora: S/17 - $4.50\n"
        "🥇 GOLD     : Antes: S/85 - $22.99 | Ahora: S/43 - $11.49\n"
        "🏆 PLATINUM : Antes: S/163 - $43.99 | Ahora: S/82 - $22\n"
        "💠 DIAMOND  : Antes: S/348 - $93.99 | Ahora: S/174 - $46.99\n\n"
        "⏳ Oferta especial por tiempo limitado.\n"
        "¿Te gustaría pagar en soles o en dólares?"
    ),
    "precio":     "💰 Escribe 'planes' para ver precios actualizados.",
    "membresía":  "Para ver nuestras membresías, escribe 'planes' o haz clic en '💎 Ver Planes'.",
    "hola":         "👋 ¡Hola! ¿Quieres activar una membresía VIP? Escribe 'planes' para empezar.",
    "buenos días":  "☀️ ¡Buenos días! ¿Quieres ver los planes disponibles?",
    "buenas tardes":"🌤 ¡Buenas tardes! ¿Te gustaría activar una membresía VIP?",
    "buenas noches":"🌙 ¡Buenas noches! ¿Quieres ver los planes disponibles?",
    "gracias":      "😊 ¡Gracias por confiar en nosotros!",
    "chau":         "👋 ¡Hasta pronto!",
}

# ============ ACTIVACIÓN DE MEMBRESÍA ============

def activar_usuario(user_id, membresia, chat_id_admin):
    try:
        plan_result = supabase_service.table('membresias_planes').select('*').eq('nombre', membresia).execute()
        if not plan_result.data:
            bot.send_message(chat_id_admin, "❌ Membresía no válida")
            return False

        plan_data = plan_result.data[0]
        duracion_plan        = plan_data['duracion_dias']
        limite_pedidos_nuevo = plan_data['pedidos_por_mes']
        es_mejora = False
        dias_extra = pedidos_extra = 0
        plan_anterior_nombre = None

        usuario_actual = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
        tiene_activa   = usuario_actual.data and usuario_actual.data[0].get('membresia_activa')

        if tiene_activa:
            usuario = usuario_actual.data[0]
            fecha_venc = datetime.fromisoformat(usuario['fecha_vencimiento'])
            dias_rest  = (fecha_venc - datetime.now()).days
            if dias_rest > 0:
                es_mejora = True
                dias_extra = dias_rest
                plan_anterior_nombre = usuario.get('membresia_tipo', 'anterior')
                mem_ant = supabase_service.table('membresias_activas') \
                    .select('fecha_inicio, plan_id').eq('usuario_id', usuario['id']).eq('estado', 'activa').execute()
                if mem_ant.data:
                    fecha_ini_ant  = datetime.fromisoformat(mem_ant.data[0]['fecha_inicio'])
                    pedidos_usados = supabase_service.table('pedidos').select('*', count='exact') \
                        .eq('usuario_id', user_id) \
                        .gte('fecha_pedido', fecha_ini_ant.isoformat()) \
                        .lte('fecha_pedido', datetime.now().isoformat()).execute()
                    usados = pedidos_usados.count if hasattr(pedidos_usados, 'count') else len(pedidos_usados.data)
                    plan_ant = supabase_service.table('membresias_planes').select('pedidos_por_mes') \
                        .eq('id', mem_ant.data[0]['plan_id']).execute()
                    limite_ant = plan_ant.data[0]['pedidos_por_mes'] if plan_ant.data else 0
                    pedidos_extra = max(0, limite_ant - usados)

        fecha_vencimiento = datetime.now() + timedelta(days=duracion_plan + dias_extra)
        nombre = usuario_actual.data[0].get('nombre', f"Usuario_{user_id}") if usuario_actual.data else f"Usuario_{user_id}"

        supabase_service.table('usuarios').upsert({
            "telegram_id": user_id, "nombre": nombre,
            "membresia_tipo": membresia, "membresia_activa": True,
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "pedidos_mes": 0
        }, on_conflict='telegram_id').execute()

        usuario_id = supabase_service.table('usuarios').select('id').eq('telegram_id', user_id).execute().data[0]['id']

        # ✅ Resetear flags de notificación para el nuevo período
        _resetear_notifs(usuario_id)

        supabase_service.table('membresias_activas').update({"estado": "inactiva"}) \
            .eq('usuario_id', usuario_id).eq('estado', 'activa').execute()
        supabase_service.table('membresias_activas').insert({
            "usuario_id": usuario_id, "plan_id": plan_data['id'],
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": fecha_vencimiento.isoformat(),
            "estado": "activa", "metodo_pago": "auto",
            "monto": plan_data['precio_soles'], "pedidos_extra": pedidos_extra
        }).execute()

        # ✅ FIX: SIEMPRE desbanear antes de enviar enlaces,
        # sin importar si tiene_activa es True o False.
        # Si el usuario renovó tarde (ya fue baneado por vencimiento),
        # el unban es necesario para que el enlace de invitación funcione.
        # Si nunca fue baneado, unban_chat_member lo ignora sin errores.
        desbanear_usuario(user_id)

        if not tiene_activa:
            try:
                exp = int(time.time()) + 604800  # 7 días
                inv_pelis  = bot.create_chat_invite_link(CANAL_PELICULAS_ID, name=f"U{user_id}_pelis",  member_limit=1, expire_date=exp)
                inv_series = bot.create_chat_invite_link(CANAL_SERIES_ID,    name=f"U{user_id}_series", member_limit=1, expire_date=exp)
                inv_grupo  = bot.create_chat_invite_link(GRUPO_CONTENIDO_ID, name=f"U{user_id}_grupo",  member_limit=1, expire_date=exp)
                markup = InlineKeyboardMarkup(row_width=1)
                markup.add(
                    InlineKeyboardButton("🎬 Canal de Películas", url=inv_pelis.invite_link),
                    InlineKeyboardButton("📺 Canal de Series",    url=inv_series.invite_link),
                    InlineKeyboardButton("📘 Grupo Bíblico Vip",  url=inv_grupo.invite_link),
                )
                if CANAL_ANIME_ID:
                    try:
                        inv_anime = bot.create_chat_invite_link(CANAL_ANIME_ID, name=f"U{user_id}_anime", member_limit=1, expire_date=exp)
                        markup.add(InlineKeyboardButton("📺 Grupo Series V2", url=inv_anime.invite_link))
                    except Exception as e_anime:
                        print(f"⚠️ No se pudo crear enlace de anime: {e_anime}")
                bot.send_message(user_id,
                    "🔐 <b>ACCESO A TUS CANALES</b>\n\n"
                    "👇 Toca los botones para unirte\n\n"
                    "⚠️ Enlaces de uso único - expiran en 7 días",
                    parse_mode="HTML", reply_markup=markup)
                canales_n = "4" if CANAL_ANIME_ID else "3"
                bot.send_message(user_id, f"📍 Únete a los {canales_n} canales, silencialos y usa la MiniApp para ver el contenido.")
                bot.send_message(chat_id_admin, f"✅ Usuario {user_id} activado — unban + {canales_n} enlaces enviados")
            except Exception as e:
                bot.send_message(chat_id_admin, f"⚠️ Membresía activada pero error con enlaces: {e}")
        else:
            bot.send_message(chat_id_admin, f"✅ Usuario {user_id} mejoró a {membresia} (ya está en canales, se hizo unban preventivo)")

        total_pedidos = limite_pedidos_nuevo + pedidos_extra
        if es_mejora:
            mensaje = (
                f"🔄 *¡Mejoraste a {membresia.upper()}!*\n\n"
                f"Hemos sumado los {dias_extra} días restantes de tu plan {plan_anterior_nombre.capitalize()} "
                f"y tus {pedidos_extra} pedidos no usados.\n"
                f"📅 *Nueva fecha de vencimiento:* {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"🎟 *Pedidos disponibles:* {total_pedidos}\n\n"
                "¡Gracias por confiar en nosotros!"
            )
        else:
            mensaje = (
                f"🎉 *¡Membresía Activada!*\n\n"
                f"💎 Plan: {membresia.upper()}\n"
                f"📅 Vence: {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"🎟 Pedidos por mes: {limite_pedidos_nuevo}"
            )
        bot.send_message(user_id, mensaje, parse_mode="Markdown")
        return True

    except Exception as e:
        bot.send_message(chat_id_admin, f"❌ Error en activación: {str(e)}")
        return False

# ============ COMANDOS ADMIN ============

@bot.message_handler(commands=['activar'])
def activar(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 3:
        bot.reply_to(message, "❌ Usa: /activar USER_ID PLAN"); return
    try:
        activar_usuario(int(partes[1]), partes[2].lower(), message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['auto_activar'])
def auto_activar(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 3:
        bot.reply_to(message, "❌ Usa: /auto_activar USER_ID PLAN"); return
    try:
        activar_usuario(int(partes[1]), partes[2].lower(), message.chat.id)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['activos'])
def listar_activos(message):
    if not is_admin(message.from_user.id):
        return
    usuarios = supabase_service.table('usuarios').select('telegram_id,nombre,membresia_tipo,fecha_vencimiento') \
        .eq('membresia_activa', True).execute()
    if not usuarios.data:
        bot.send_message(message.chat.id, "📭 No hay usuarios activos"); return
    msg = "📋 *USUARIOS CON MEMBRESÍA ACTIVA:*\n\n"
    for u in usuarios.data:
        vence = u.get('fecha_vencimiento', '')[:10]
        msg += f"👤 ID: `{u['telegram_id']}` | {u.get('nombre','N/A')} | 💎 {u.get('membresia_tipo','?')} | 📅 {vence}\n"
    msg += f"\n📊 Total: {len(usuarios.data)} usuarios"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['desactivar'])
def desactivar(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 2:
        bot.send_message(message.chat.id, "❌ Usa: /desactivar ID"); return
    try:
        uid = int(partes[1])
        usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', uid).execute()
        if not usuario.data:
            bot.send_message(message.chat.id, f"❌ Usuario {uid} no encontrado"); return
        uid_interno = usuario.data[0]['id']
        supabase_service.table('usuarios').update({"membresia_activa": False}).eq('telegram_id', uid).execute()
        supabase_service.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', uid_interno).eq('estado','activa').execute()
        bot.send_message(message.chat.id, f"✅ Usuario {uid} desactivado")
        try:
            bot.send_message(uid, "⚠️ Tu membresía ha sido desactivada.")
        except:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['generar_enlaces'])
def generar_enlaces(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(message, "❌ Usa: /generar_enlaces USER_ID"); return
    try:
        uid = int(partes[1])
        desbanear_usuario(uid)
        exp_ts = int(time.time()) + 604800
        inv_pelis  = bot.create_chat_invite_link(CANAL_PELICULAS_ID, name=f"U{uid}_pelis",  member_limit=1, expire_date=exp_ts)
        inv_series = bot.create_chat_invite_link(CANAL_SERIES_ID,    name=f"U{uid}_series", member_limit=1, expire_date=exp_ts)
        inv_grupo  = bot.create_chat_invite_link(GRUPO_CONTENIDO_ID, name=f"U{uid}_grupo",  member_limit=1, expire_date=exp_ts)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🎬 Canal de Películas", url=inv_pelis.invite_link),
            InlineKeyboardButton("📺 Canal de Series",    url=inv_series.invite_link),
            InlineKeyboardButton("👥 Grupo Privado",      url=inv_grupo.invite_link),
        )
        if CANAL_ANIME_ID:
            try:
                inv_anime = bot.create_chat_invite_link(CANAL_ANIME_ID, name=f"U{uid}_anime", member_limit=1, expire_date=exp_ts)
                markup.add(InlineKeyboardButton("📺 Grupo Series V2", url=inv_anime.invite_link))
            except Exception as e_anime:
                print(f"⚠️ Error enlace anime: {e_anime}")
        bot.send_message(uid,
            "🔐 <b>ACCESO A TUS CANALES</b>\n\n"
            "👇 Toca los botones para unirte\n\n"
            "⚠️ Enlaces de uso único - expiran en 7 días",
            parse_mode="HTML", reply_markup=markup)
        bot.reply_to(message, f"✅ {'4' if CANAL_ANIME_ID else '3'} enlaces enviados a {uid}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['reactivar'])
def reactivar(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 3:
        bot.send_message(message.chat.id, "❌ Usa: /reactivar ID PLAN"); return
    try:
        activar_usuario(int(partes[1]), partes[2].lower(), message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['id'])
def get_id(message):
    bot.reply_to(message, f"Chat ID: `{message.chat.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['reply'])
def reply_directo(message):
    if message.chat.id != GRUPO_SOPORTE_ID and not is_admin(message.from_user.id):
        return
    partes = message.text.split(None, 2)
    if len(partes) < 3:
        bot.reply_to(message, "❌ Uso: /reply ID_USUARIO mensaje\nEj: /reply 5824989040 Ya activé tu membresía.")
        return
    try:
        uid = int(partes[1])
        bot.send_message(uid, f"📝 *Respuesta de soporte:*\n\n{partes[2]}", parse_mode="Markdown")
        bot.reply_to(message, f"✅ Mensaje enviado a {uid}.")
    except ValueError:
        bot.reply_to(message, "❌ El ID debe ser un número.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['publicar'])
def publicar_manual(message):
    if not is_admin(message.from_user.id):
        return
    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(message, "❌ Usa: /publicar ID_CONTENIDO"); return
    try:
        cid = int(partes[1])
        res = supabase_service.table("contenido").select("*").eq("id", cid).execute()
        if not res.data:
            bot.reply_to(message, f"❌ Contenido {cid} no encontrado"); return
        item = res.data[0]
        bot.reply_to(message, f"⏳ Publicando '{item['titulo']}' en los canales...")
        ok = enviar_contenido_al_canal(item)
        if ok:
            registrar_publicacion(cid)
            bot.reply_to(message, f"✅ Publicado correctamente: {item['titulo']}")
        else:
            bot.reply_to(message,
                f"❌ Error al publicar.\n"
                f"Verifica que el bot @{BOT_USERNAME} sea admin en:\n"
                f"• {CANAL_PUBLICO_ID}\n• {CANAL_PRIVADO_ID}"
            )
    except ValueError:
        bot.reply_to(message, "❌ El ID debe ser un número. Ej: /publicar 428")
    except Exception as e:
        bot.reply_to(message, f"❌ Error inesperado: {e}")

# ============ FLASK APP ============
from marketing import marketing_bp, init_marketing, enviar_email as _enviar_email_mkt, _html_bienvenida as _html_bienvenida_mkt

app = Flask(__name__)
CORS(app)

app.register_blueprint(marketing_bp)
init_marketing(supabase_service, bot, ADMIN_IDS, BOT_USERNAME)

@app.route("/")
def serve_miniapp():
    return send_from_directory("static", "index.html")

@app.route("/admin")
def serve_admin():
    return send_from_directory("static", "admin.html")

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    """Login del panel de administración. Valida ID + contraseña en backend."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        admin_id = int(data.get("admin_id", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "ID inválido"}), 400
    password = str(data.get("password", ""))

    if not ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "ADMIN_PASSWORD no configurado en el servidor"}), 500
    if admin_id not in ADMIN_IDS or password != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "ID o contraseña incorrectos"}), 401

    return jsonify({"success": True}), 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ============ ENDPOINTS ============

@app.route("/aprobar_pago", methods=["POST"])
def aprobar_pago():
    try:
        data    = request.get_json()
        pago_id = data.get("pagoId")
        if not pago_id:
            return jsonify({"error": "pagoId requerido"}), 400
        pago = supabase_service.table("pagos_manuales").select("*").eq("id", pago_id).execute()
        if not pago.data:
            return jsonify({"error": "Pago no encontrado"}), 404
        pago = pago.data[0]
        ok = activar_usuario(pago["usuario_id"], pago["membresia_comprada"].lower(), ADMIN_ID)
        if not ok:
            return jsonify({"error": "Error activando"}), 500
        supabase_service.table("pagos_manuales").update({"estado": "aprobado", "activado": True}).eq("id", pago_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/crear_pago_tarjeta", methods=["POST"])
def crear_pago_tarjeta():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        plan  = data.get("plan")
        email = data.get("email")
        if not all([telegram_id, plan, email]):
            return jsonify({"error": "Datos incompletos"}), 400
        supabase_service.table("usuarios").update({"email": email}).eq("telegram_id", telegram_id).execute()
        supabase_service.table("pagos_manuales").insert({
            "usuario_id": telegram_id, "membresia_comprada": plan.lower(),
            "metodo": "tarjeta", "estado": "pendiente_webhook",
            "activado": False, "email": email,
            "fecha_pago": datetime.now().isoformat()
        }).execute()
        return jsonify({"success": True, "url": BMC_LINKS.get(plan.lower())}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        if admin_id not in ADMIN_IDS:
            return jsonify({"error": f"No autorizado (got {admin_id}, expected one of {list(ADMIN_IDS)})"}), 403
        if not tmdb_id:
            return jsonify({"error": "tmdb_id requerido o invalido"}), 400
        if tipo not in ("pelicula", "serie", "anime"):
            return jsonify({"error": f"tipo invalido: '{tipo}'. Debe ser: pelicula, serie o anime"}), 400
        if not TMDB_API_KEY:
            return jsonify({"error": "TMDB_API_KEY no configurada en el servidor"}), 500
        contenido = importar_desde_tmdb(int(tmdb_id), tipo)
        existe = supabase_service.table("contenido").select("id").eq("tmdb_id", int(tmdb_id)).execute()
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
        resultado = importar_temporadas_desde_tmdb(int(tmdb_id), contenido_id)
        return jsonify({"success": True, **resultado}), 200
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
    try:
        body_bytes = request.get_data()
        data       = request.get_json(force=True, silent=True) or {}
        event_type = data.get("event_type", "")
        print(f"DEBUG PayPal webhook event: {event_type}")

        if event_type == "BILLING.SUBSCRIPTION.CREATED":
            print("ℹ️ Suscripción creada")
            return jsonify({"success": True}), 200

        if not paypal_verificar_webhook(request.headers, body_bytes):
            return jsonify({"error": "Verificación fallida"}), 400

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            resource    = data.get("resource", {})
            custom_id   = resource.get("custom_id", "")
            payer_email = (resource.get("payer", {}) or {}).get("email_address", "")
            amount      = resource.get("amount", {}).get("value", "0")
            if not custom_id:
                units     = resource.get("purchase_units", [{}])
                custom_id = units[0].get("custom_id", "") if units else ""
            partes = custom_id.split("|")
            if len(partes) < 2:
                return jsonify({"error": "custom_id inválido"}), 400
            telegram_id = int(partes[0])
            plan        = partes[1].lower()
            if payer_email:
                supabase_service.table("usuarios").update({"email": payer_email}).eq("telegram_id", telegram_id).execute()
            supabase_service.table("pagos_manuales").insert({
                "usuario_id": telegram_id, "membresia_comprada": plan,
                "monto": float(amount), "metodo": "paypal",
                "estado": "aprobado", "activado": False,
                "email": payer_email or None,
                "fecha_pago": datetime.now().isoformat(), "recordatorio_enviado": True,
            }).execute()
            ok = activar_usuario(telegram_id, plan, ADMIN_ID)
            if ok:
                supabase_service.table("pagos_manuales").update({"activado": True}) \
                    .eq("usuario_id", telegram_id).eq("metodo", "paypal") \
                    .eq("estado", "aprobado").eq("activado", False).execute()
                if payer_email:
                    nr = supabase_service.table("usuarios").select("nombre").eq("telegram_id", telegram_id).execute()
                    nombre = nr.data[0]["nombre"] if nr.data else "VIP"
                    _enviar_email_mkt(payer_email, "🎉 ¡Membresía activada!", _html_bienvenida_mkt(nombre, plan, BOT_USERNAME))

        elif event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RENEWED"):
            resource        = data.get("resource", {})
            subscription_id = resource.get("id", "")
            custom_id       = resource.get("custom_id", "")
            payer_email     = (resource.get("subscriber", {}) or {}).get("email_address", "")
            partes = custom_id.split("|") if custom_id else []
            if len(partes) < 2:
                return jsonify({"received": True}), 200
            telegram_id = int(partes[0])
            plan        = partes[1].lower()
            amount_str  = PAYPAL_PRECIOS.get(plan, "0")
            if payer_email:
                supabase_service.table("usuarios").update({
                    "email": payer_email, "paypal_subscription_id": subscription_id
                }).eq("telegram_id", telegram_id).execute()
            supabase_service.table("pagos_manuales").insert({
                "usuario_id": telegram_id, "membresia_comprada": plan,
                "monto": float(amount_str), "metodo": "paypal_subscription",
                "estado": "aprobado", "activado": False,
                "email": payer_email or None,
                "fecha_pago": datetime.now().isoformat(), "recordatorio_enviado": True,
            }).execute()
            ok = activar_usuario(telegram_id, plan, ADMIN_ID)
            if ok:
                supabase_service.table("pagos_manuales").update({"activado": True}) \
                    .eq("usuario_id", telegram_id).eq("metodo", "paypal_subscription") \
                    .eq("estado", "aprobado").eq("activado", False).execute()
                if payer_email:
                    nr = supabase_service.table("usuarios").select("nombre").eq("telegram_id", telegram_id).execute()
                    nombre = nr.data[0]["nombre"] if nr.data else "VIP"
                    _enviar_email_mkt(payer_email, "🎉 ¡Suscripción activada!", _html_bienvenida_mkt(nombre, plan, BOT_USERNAME))
                tipo_msg = "renovada" if event_type == "BILLING.SUBSCRIPTION.RENEWED" else "activada"
                try:
                    bot.send_message(telegram_id,
                        f"🔄 *¡Suscripción {tipo_msg}!*\n\n"
                        f"💎 Plan: *{plan.upper()}*\n"
                        "📅 Tu membresía se renueva automáticamente cada mes.\n\n"
                        "Para cancelar en cualquier momento escribe /cancelar\\_suscripcion",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"⚠️ No se pudo notificar a {telegram_id}: {e}")

        elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.SUSPENDED"):
            resource        = data.get("resource", {})
            subscription_id = resource.get("id", "")
            custom_id       = resource.get("custom_id", "")
            partes = custom_id.split("|") if custom_id else []
            if len(partes) >= 1:
                try:
                    telegram_id = int(partes[0])
                    try:
                        bot.send_message(telegram_id,
                            "⚠️ *Suscripción cancelada*\n\n"
                            "Tu suscripción fue cancelada. Seguirás teniendo acceso hasta que venza tu período actual.\n\n"
                            "Puedes renovar cuando quieras desde la Mini App.",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                except Exception as e:
                    print(f"⚠️ Error procesando cancelación: {e}")

        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"❌ PayPal webhook error: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

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
    try:
        data        = request.get_json(force=True, silent=True) or {}
        telegram_id = data.get("telegram_id")
        plan        = data.get("plan", "").lower()
        email       = data.get("email", "")
        modo        = data.get("modo", "unico")
        if not telegram_id or not plan:
            return jsonify({"error": "telegram_id y plan requeridos"}), 400
        if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
            return jsonify({"error": "PayPal no configurado en el servidor"}), 500
        if email:
            supabase_service.table("usuarios").update({"email": email}).eq("telegram_id", telegram_id).execute()
        if modo == "suscripcion":
            plan_id = PAYPAL_PLAN_IDS.get(plan, "")
            if not plan_id:
                return jsonify({
                    "error": f"Suscripción no configurada para el plan '{plan}'. "
                             f"Agrega PAYPAL_PLAN_ID_{plan.upper()} en Render."
                }), 400
            sub = paypal_crear_suscripcion(plan, int(telegram_id), email)
            supabase_service.table("pagos_manuales").insert({
                "usuario_id": telegram_id, "membresia_comprada": plan,
                "monto": float(PAYPAL_PRECIOS.get(plan, 0)),
                "metodo": "paypal_subscription", "estado": "pendiente_webhook",
                "activado": False, "email": email or None,
                "fecha_pago": datetime.now().isoformat(), "recordatorio_enviado": False,
            }).execute()
            return jsonify({"success": True, "url": sub["approve_url"], "subscription_id": sub["subscription_id"], "tipo": "suscripcion"}), 200
        else:
            orden = paypal_crear_orden(plan, int(telegram_id), email)
            supabase_service.table("pagos_manuales").insert({
                "usuario_id": telegram_id, "membresia_comprada": plan,
                "monto": float(PAYPAL_PRECIOS.get(plan, 0)),
                "metodo": "paypal", "estado": "pendiente_webhook",
                "activado": False, "email": email or None,
                "fecha_pago": datetime.now().isoformat(), "recordatorio_enviado": False,
            }).execute()
            return jsonify({"success": True, "url": orden["approve_url"], "order_id": orden["order_id"], "tipo": "unico"}), 200
    except requests.HTTPError as e:
        return jsonify({"error": f"PayPal API error {e.response.status_code}"}), 400
    except Exception as e:
        print(f"❌ crear_pago_paypal: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

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
        return "OK", 200
    except Exception as e:
        return "Error", 500

# ============================================================
# FIX COMPLETO: verificar_vencimientos
# Bugs corregidos:
# 1. Ahora filtra por notificacion_3dias_enviada=False antes de enviar
#    → evita reenvíos cada 10 min cuando el cron pasa repetidamente
# 2. Llama a _marcar_notif() después de enviar cada tipo de notificación
#    → marca el flag en Supabase para que no se reenvíe
# 3. Nombres de columnas corregidos (notificacion_3dias_enviada, notificacion_3hora, notificacion_vencida_enviada)
# 4. Ban al vencer + desbanear al renovar ya funciona correctamente
# ============================================================
def verificar_vencimientos():
    ahora    = datetime.now()
    hoy      = ahora.isoformat()
    en_3dias = (ahora + timedelta(days=3)).isoformat()
    en_3h    = (ahora + timedelta(hours=3)).isoformat()

    # ── NOTIFICACIÓN 3 DÍAS ────────────────────────────────────────────────
    # FIX: filtrar solo usuarios que AÚN NO recibieron esta notificación
    proximos_3dias = supabase_service.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .eq("notificacion_3dias_enviada", False) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3dias) \
        .execute()

    for u in proximos_3dias.data:
        try:
            vence = datetime.fromisoformat(u["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
            bot.send_message(
                u["telegram_id"],
                f"⏳ *Tu membresía vence en 3 días* ({vence}).\n"
                "Renueva para no perder el acceso.\n\n"
                "👇 Presiona para renovar:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("💎 Renovar membresía",
                        web_app=telebot.types.WebAppInfo(url=f"{MINIAPP_URL}?seccion=membresias"))
                )
            )
            # FIX: marcar en Supabase con el nombre correcto de columna
            _marcar_notif(u["id"], "notificacion_3dias_enviada")
            print(f"✅ Notif 3días enviada a {u['telegram_id']}")
        except Exception as e:
            print(f"⚠️ Error notif 3días a {u['telegram_id']}: {e}")

    # ── NOTIFICACIÓN 3 HORAS ───────────────────────────────────────────────
    # FIX: filtrar solo usuarios que AÚN NO recibieron esta notificación
    proximos_3h = supabase_service.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .eq("notificacion_3horas_enviada", False) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3h) \
        .execute()

    for u in proximos_3h.data:
        try:
            vence = datetime.fromisoformat(u["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
            bot.send_message(
                u["telegram_id"],
                f"⚠️ *¡Tu membresía vence en 3 horas!* ({vence}).\n"
                "Renueva ahora para mantener el acceso sin interrupciones.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("💎 Renovar ahora",
                        web_app=telebot.types.WebAppInfo(url=f"{MINIAPP_URL}?seccion=membresias"))
                )
            )
            # FIX: marcar en Supabase con el nombre correcto de columna
            _marcar_notif(u["id"], "notificacion_3horas_enviada")
            print(f"✅ Notif 3h enviada a {u['telegram_id']}")
        except Exception as e:
            print(f"⚠️ Error notif 3h a {u['telegram_id']}: {e}")

    # ── VENCIMIENTOS (ban + notificación) ─────────────────────────────────
    vencidos = supabase_service.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", hoy) \
        .execute()

    for u in vencidos.data:
        try:
            # Desactivar membresía en BD
            supabase_service.table("usuarios").update({"membresia_activa": False}) \
                .eq("id", u["id"]).execute()
            supabase_service.table("membresias_activas").update({"estado": "inactiva"}) \
                .eq("usuario_id", u["id"]).eq("estado", "activa").execute()

            # Banear de todos los canales VIP
            for canal in CANALES_VIP:
                try:
                    bot.ban_chat_member(chat_id=canal, user_id=u["telegram_id"])
                    print(f"🔨 Baneado {u['telegram_id']} de {canal}")
                except Exception as e_ban:
                    print(f"⚠️ Ban fallido {u['telegram_id']} en {canal}: {e_ban}")

            # Notificar al usuario solo si no se notificó antes
            if not u.get("notificacion_vencida_enviada", False):
                try:
                    bot.send_message(
                        u["telegram_id"],
                        "❌ *Tu membresía ha vencido.*\n\n"
                        "Tu acceso a los canales ha sido suspendido.\n"
                        "Renueva para volver a disfrutar del contenido.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("💎 Renovar membresía",
                                web_app=telebot.types.WebAppInfo(url=f"{MINIAPP_URL}?seccion=membresias"))
                        )
                    )
                    # FIX: marcar notificación de vencimiento enviada
                    _marcar_notif(u["id"], "notificacion_vencida_enviada")
                    print(f"✅ Notif vencida enviada a {u['telegram_id']}")
                except Exception as e_msg:
                    print(f"⚠️ No se pudo notificar vencimiento a {u['telegram_id']}: {e_msg}")

        except Exception as e:
            print(f"⚠️ Error procesando vencimiento de {u.get('telegram_id')}: {e}")


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
    planes = supabase_service.table("membresias_planes").select("*").execute()
    return jsonify(planes.data)

@app.route("/api/contenido", methods=["POST"])
def api_contenido():
    data     = request.get_json()
    busqueda = data.get("busqueda","")
    tipo     = data.get("tipo","todo")
    limit    = int(data.get("limit",20))
    offset   = int(data.get("offset",0))
    query = supabase_service.table("contenido").select("*", count="exact").eq("disponible", True)
    if tipo != "todo":
        query = query.eq("tipo", tipo)
    if busqueda:
        query = query.ilike("titulo", f"%{busqueda}%")
    genero = data.get("genero")
    if genero:
        query = query.ilike("genero", f"%{genero}%")
    if data.get("descarga"):
        query = query.not_.is_("descarga","null").neq("descarga","")
    resultados = query.order("id", desc=True).range(offset, offset+limit-1).execute()
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
    view_key = os.getenv("VIMEUS_VIEW_KEY")
    return jsonify({"view_key": view_key}) if view_key else (jsonify({"error": "No configurada"}), 404)

@app.route("/api/tendencias", methods=["GET"])
def api_tendencias():
    resultados = supabase_service.table("contenido").select("*") \
        .eq("destacado", True).order("orden_destacado").limit(10).execute()
    return jsonify(resultados.data)

@app.route("/webhook/buymeacoffee", methods=["POST"])
def webhook_buymeacoffee():
    try:
        data = request.get_json()
        tipo_evento = data.get("type")
        datos = data.get("data",{})
        email = datos.get("supporter_email")
        if not email:
            return jsonify({"error": "Email no encontrado"}), 400
        pago_res = supabase_service.table("pagos_manuales").select("*") \
            .eq("email", email).eq("estado","pendiente_webhook").execute()
        if not pago_res.data:
            return jsonify({"error": "No hay pago pendiente"}), 400
        registro_pago = pago_res.data[0]
        telegram_id   = registro_pago["usuario_id"]
        plan_comprado = registro_pago["membresia_comprada"].lower()
        plan_detectado = None
        if tipo_evento in ["membership.started","membership.updated"]:
            if datos.get("estado") == "active" and not datos.get("cancelado") and not datos.get("cancel_at_period_end"):
                plan_detectado = datos.get("membership_level_name","").lower()
        elif tipo_evento == "extra_purchase.created":
            extras = datos.get("extras",[])
            if extras:
                product_to_plan = {"517243":"copper","517244":"silver","510546":"gold","510549":"platinum","510552":"diamond"}
                plan_detectado = product_to_plan.get(str(extras[0].get("id")))
        elif tipo_evento in ["membership.cancelled"]:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": True}), 200
        if not plan_detectado or plan_detectado != plan_comprado:
            return jsonify({"error": "Plan no coincide"}), 400
        ok = activar_usuario(telegram_id, plan_comprado, ADMIN_ID)
        if not ok:
            return jsonify({"error": "Error activando"}), 500
        supabase_service.table("pagos_manuales").update({"estado":"aprobado","activado":True}).eq("id",registro_pago["id"]).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ INICIO ============

if __name__ == "__main__":
    print("🚀 Bot iniciado con Webhook...")
    bot.remove_webhook()
    bot.set_webhook(url=os.getenv("RENDER_EXTERNAL_URL") + f"/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))