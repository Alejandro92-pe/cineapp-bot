"""
CineApp Bot - Aplicación Principal Refactorizada
Flask + Telebot + Supabase

Arquitectura Modular:
  - config/: Configuración
  - services/: Lógica de negocio (membresías, notificaciones, contenido)
  - handlers/: Handlers de Telegram
  - routes/: Endpoints Flask
  - utils/: Funciones utilitarias
"""

import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)
from datetime import datetime, timedelta, timezone
import time
import requests
import json
import logging

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ IMPORTAR CONFIGURACIÓN ============
from config import (
    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_KEY,
    BOT_TOKEN, ADMIN_ID, TMDB_API_KEY, BOT_USERNAME,
    RENDER_EXTERNAL_URL, LIMA_TZ,
    MINIAPP_URL, BMC_LINKS, BMC_URL,
    CANAL_PUBLICO_ID, CANAL_PRIVADO_ID,
    CANAL_PELICULAS_ID, CANAL_SERIES_ID, GRUPO_CONTENIDO_ID, GRUPO_SOPORTE_ID,
    TIPO_TMDB, TMDB_BASE, TMDB_IMG
)

# ============ IMPORTAR SERVICIOS ============
from services.notifications import verificar_vencimientos
from services.membership import activar_usuario
from services.content import (
    obtener_siguiente_contenido_a_publicar,
    registrar_publicacion,
    importar_desde_tmdb,
    enviar_contenido_al_canal,
    generar_estrellas,
    construir_caption,
    construir_botones_canal
)

# ============ IMPORTAR BLUEPRINTS ============
from routes.cron import cron_bp, membership_bp

# ============ IMPORTAR UTILITIES ============
from utils.helpers import check_admin, tmdb_get

# ============ INICIALIZAR ============
from supabase import create_client
supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# ============ VARIABLES GLOBALES ============
user_states = {}

# ============ REGISTRAR BLUEPRINTS ============
app.register_blueprint(cron_bp)
app.register_blueprint(membership_bp)

# ============ KEYWORD REPLIES ============
KEYWORD_REPLIES = {
    "quiero comprar": "🛒 ¡Perfecto! ¿Qué plan deseas activar? Silver, Gold, Platinum o Diamond.\n\nPuedes pagar en *soles* (Yape/Plin) o en *dólares* (tarjeta automática).",
    "planes": (
        "💎 *PLANES DISPONIBLES — 50% OFF* 💎\n\n"
        "🥉 COPPER: S/11 - $3\n"
        "🥈 SILVER: S/17 - $4.50\n"
        "🥇 GOLD: S/43 - $11.49\n"
        "🏆 PLATINUM: S/82 - $22\n"
        "💠 DIAMOND: S/174 - $46.99"
    ),
    "beneficios": (
        "✨ *BENEFICIOS VIP* ✨\n\n"
        "🔐 Acceso privado\n"
        "📥 Descargas directas\n"
        "🚫 Sin publicidad\n"
        "🎞 Contenido exclusivo\n"
        "📦 Pedidos según plan"
    ),
    "ayuda": "🆘 Describe tu problema y soporte te responderá lo antes posible.",
}

# ============ MENÚ PRINCIPAL ============
def menu_principal(chat_id, user_name=""):
    """Envía el menú principal al usuario"""
    texto = (
        f"🎬 *¡Bienvenido {user_name} a QuehayApp VIP!*\n\n"
        "👇 *Selecciona una opción:*"
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💎 Ver Planes", "🎬 Beneficios VIP")
    markup.row("⭐ Testimonios", "💰 Cómo pagar")
    markup.row("📱 Mini App Vip", "🆘 Ayuda")
    bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

# ============ /start COMANDO ============
@bot.message_handler(commands=['start'])
def start(message):
    """Maneja el comando /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id

    # Registrar usuario si no existe
    usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
    if not usuario.data:
        supabase_service.table('usuarios').insert({
            "telegram_id": user_id,
            "nombre": user_name,
            "membresia_activa": False,
            "notificacion_3dias_enviada": False,
            "notificacion_3horas_enviada": False,
            "notificacion_vencida_enviada": False
        }).execute()
        logger.info(f"✅ Usuario nuevo registrado: {user_id}")

    args = message.text.split()

    # Deep link: pago_plan_precio
    if len(args) > 1 and args[1].startswith("pago_"):
        partes = args[1].split("_")
        if len(partes) == 3:
            plan = partes[1]
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

    # Deep link: miniapp
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
            web_app=WebAppInfo(url=MINIAPP_URL)
        ))
        bot.send_message(chat_id, texto, parse_mode="Markdown", reply_markup=markup)
        return

    # Deep link: planes
    if len(args) > 1 and args[1] == "planes":
        bot.send_message(chat_id, KEYWORD_REPLIES["planes"], parse_mode="Markdown")
        return

    # Menú por defecto
    menu_principal(chat_id, user_name)

# ============ BOTONES DEL MENÚ ============
@bot.message_handler(func=lambda m: m.text == "💎 Ver Planes")
def ver_planes(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["planes"], parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎬 Beneficios VIP")
def beneficios(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["beneficios"], parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🆘 Ayuda")
def ayuda(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["ayuda"], parse_mode="Markdown")

# ============ CALLBACKS ============
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Maneja todos los callbacks"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data
    bot.answer_callback_query(call.id)

    if data == "cancelar_voucher":
        if user_id in user_states:
            del user_states[user_id]
        supabase_service.table('pagos_manuales') \
            .update({"estado": "cancelado"}) \
            .eq("usuario_id", user_id).eq("estado", "pendiente").execute()
        bot.send_message(chat_id, "✅ Pago cancelado.")

# ============ FOTOS (Voucher) ============
@bot.message_handler(content_types=['photo'])
def recibir_foto(message):
    """Maneja fotos de vouchers"""
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
    
    bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    bot.send_message(chat_id, "📩 Tu imagen fue enviada a soporte.")

# ============ TEXTO LIBRE ============
@bot.message_handler(content_types=['text'])
def manejar_texto(message):
    """Maneja mensajes de texto"""
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_original = message.text.strip()
    text = text_original.lower()

    # Ignorar comandos
    if text_original.startswith("/"):
        return

    # Esperar voucher
    if user_id in user_states and user_states[user_id]["estado"] == "esperando_voucher":
        bot.send_message(chat_id, "❌ Envía una FOTO del voucher o presiona Cancelar.")
        return

    # Buscar en keywords
    for keyword in sorted(KEYWORD_REPLIES.keys(), key=len, reverse=True):
        if keyword in text:
            bot.send_message(chat_id, KEYWORD_REPLIES[keyword], parse_mode="Markdown")
            return

    # Enviar a soporte
    bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    bot.send_message(chat_id, "📩 Tu mensaje fue enviado a soporte.")

# ============ COMANDOS ADMIN ============

@bot.message_handler(commands=['activar'])
def activar(message):
    """Activa membresía: /activar USER_ID PLAN"""
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split()
    if len(partes) < 3:
        bot.reply_to(message, "❌ Usa: /activar USER_ID PLAN")
        return
    try:
        activar_usuario(int(partes[1]), partes[2].lower(), message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")
        logger.error(f"Error en /activar: {e}")

@bot.message_handler(commands=['activos'])
def listar_activos(message):
    """Lista usuarios activos: /activos"""
    if message.from_user.id != ADMIN_ID:
        return
    usuarios = supabase_service.table('usuarios').select('telegram_id,nombre,membresia_tipo,fecha_vencimiento') \
        .eq('membresia_activa', True).execute()
    if not usuarios.data:
        bot.send_message(message.chat.id, "📭 No hay usuarios activos")
        return
    msg = "📋 *USUARIOS CON MEMBRESÍA ACTIVA:*\n\n"
    for u in usuarios.data:
        vence = u.get('fecha_vencimiento', '')[:10]
        msg += f"👤 ID: `{u['telegram_id']}` | {u.get('nombre','N/A')} | 💎 {u.get('membresia_tipo','?')} | 📅 {vence}\n"
    msg += f"\n📊 Total: {len(usuarios.data)} usuarios"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['publicar'])
def publicar_manual(message):
    """Publica manualmente: /publicar ID_CONTENIDO"""
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(message, "❌ Usa: /publicar ID_CONTENIDO")
        return
    try:
        cid = int(partes[1])
        res = supabase_service.table("contenido").select("*").eq("id", cid).execute()
        if not res.data:
            bot.reply_to(message, f"❌ Contenido {cid} no encontrado")
            return
        item = res.data[0]
        bot.reply_to(message, f"⏳ Publicando '{item['titulo']}'...")
        ok = enviar_contenido_al_canal(item)
        if ok:
            registrar_publicacion(cid)
            bot.reply_to(message, f"✅ Publicado: {item['titulo']}")
        else:
            bot.reply_to(message, "❌ Error al publicar.")
    except ValueError:
        bot.reply_to(message, "❌ ID debe ser número")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
        logger.error(f"Error en /publicar: {e}")

# ============ FLASK ENDPOINTS ============

@app.route("/")
def serve_miniapp():
    """Sirve la mini app"""
    return send_from_directory("static", "index.html")

@app.route("/admin")
def serve_admin():
    """Sirve el panel admin"""
    return send_from_directory("static", "admin.html")

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Webhook del bot"""
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ============ API ENDPOINTS ============

@app.route("/cron/publicar_contenido", methods=["GET"])
def cron_publicar_contenido():
    """Cron automático de publicación"""
    try:
        item = obtener_siguiente_contenido_a_publicar()
        if not item:
            return jsonify({"message": "Sin contenido disponible"}), 200
        ok = enviar_contenido_al_canal(item)
        if ok:
            registrar_publicacion(item["id"])
            logger.info(f"✅ Publicado: {item['titulo']}")
            return jsonify({"success": True, "titulo": item["titulo"]}), 200
        else:
            return jsonify({"error": "No se pudo enviar"}), 500
    except Exception as e:
        logger.error(f"Error en cron publicar: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/planes", methods=["GET"])
def api_planes():
    """Obtiene lista de planes"""
    try:
        planes = supabase_service.table("membresias_planes").select("*").execute()
        return jsonify(planes.data), 200
    except Exception as e:
        logger.error(f"Error en /api/planes: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/usuario", methods=["POST"])
def api_usuario():
    """Obtiene datos del usuario"""
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
        logger.error(f"Error en /api/usuario: {e}")
        return jsonify({"error": "Error interno"}), 500

@app.route("/aprobar_pago", methods=["POST"])
def aprobar_pago():
    """Aprueba pago manual"""
    try:
        data = request.get_json()
        if not check_admin(data):
            return jsonify({"error": "No autorizado"}), 403
        
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
        logger.info(f"✅ Pago aprobado: {pago_id}")
        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"Error en /aprobar_pago: {e}")
        return jsonify({"error": str(e)}), 500

# ============ INICIO ============

if __name__ == "__main__":
    logger.info("🚀 Bot iniciado con Webhook...")
    bot.remove_webhook()
    if RENDER_EXTERNAL_URL:
        bot.set_webhook(url=RENDER_EXTERNAL_URL + f"/{BOT_TOKEN}")
        logger.info(f"Webhook configurado en: {RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))