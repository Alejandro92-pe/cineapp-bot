from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client
from datetime import datetime, timedelta
import time
import hmac
import hashlib
import re

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
GRUPO_SOPORTE_ID = -1003805629374  
MINIAPP_URL = "https://clairvoyantly-adactylous-leonida.ngrok-free.dev"

BMC_URL = "https://buymeacoffee.com/quehay/membership"

BMC_LINKS = {
    "copper": "https://buymeacoffee.com/quehay/membership",
    "silver": "https://buymeacoffee.com/quehay/membership",
    "gold": "https://buymeacoffee.com/quehay/e/510546",
    "platinum": "https://buymeacoffee.com/quehay/e/510549",
    "diamond": "https://buymeacoffee.com/quehay/e/510552"
}

user_states = {}

# ============ CANALES PRIVADOS ============
CANAL_PELICULAS_ID = -1003890553566
CANAL_SERIES_ID = -1003879512007

# Inicializar
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

def menu_principal(chat_id, user_name=""):
    texto = (
        f"🎬 *¡Bienvenido {user_name} a QuehayApp VIP!*\n\n"
        "👇 *Selecciona una opción:*"
    )

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💎 Ver Planes", "🎬 Beneficios VIP")
    markup.row("🇵🇪 Pago en Soles", "💳 Pago en Dólares")
    markup.row("👤 Mi Perfil", "🆘 Ayuda")

    bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

#// START (con Supabase + pago)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id

    usuario = supabase_service.table('usuarios') \
        .select('*') \
        .eq('telegram_id', user_id) \
        .execute()

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

            user_states[user_id] = {
                "estado": "esperando_voucher",
                "plan": plan
            }

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("❌ Cancelar pago", callback_data="cancelar_voucher")
            )

            bot.send_message(
                chat_id,
                f"💎 *PLAN {plan.upper()}*\n\n"
                f"💰 Monto a Pagar: S/{precio}\n\n"
                "📲 *Yape/Plin:* `930202820` (Richard Quiroz)\n"
                f"📝 Concepto: {user_id}\n\n"
                "📸 Envía la captura del voucher aquí\n"
                f"✅ El sistema la enviara al admin.\n\n"
                "🟢 Despues de validar pago tu membresía se activara.",               
                parse_mode="Markdown",
                reply_markup=markup
            )
            return

    menu_principal(chat_id, user_name)

#// BOTONES DEL MENÚ

@bot.message_handler(func=lambda m: m.text == "💎 Ver Planes")
def ver_planes(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["planes"], parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎬 Beneficios VIP")
def beneficios(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["beneficios"], parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🇵🇪 Pago en Soles")
def pago_en_soles(message):
    print("✅ Handler pago_en_soles ejecutado")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Abrir Mini App", web_app={"url": MINIAPP_URL}))
    bot.send_message(message.chat.id, "🇵🇪 Paga en soles desde la mini app, ve a membresías y escoge tu plan", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "💳 Pago en Dólares")
def pago_dolares(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Pagar ahora", url=BMC_URL))
    bot.send_message(message.chat.id, "💳 Paga en dólares con tarjeta, Gpay, ApplePay, Link y mas", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "👤 Mi Perfil")
def perfil(message):
    print("✅ Handler perfil ejecutado")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Abrir perfil", web_app={"url": MINIAPP_URL}))
    bot.send_message(message.chat.id, "Consulta tu perfil:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "🆘 Ayuda")
def ayuda(message):
    bot.send_message(message.chat.id, KEYWORD_REPLIES["ayuda"], parse_mode="Markdown")

#// CALLBACKS INLINE

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    bot.answer_callback_query(call.id)

    # ==============================
    # 🔹 PAGO GENERAL EN SOLES
    # ==============================
    if data == "pago_soles_general":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🛒 Abrir Mini App", web_app={"url": MINIAPP_URL})
        )
        bot.send_message(chat_id, "🇵🇪 Paga en soles desde la mini app:", reply_markup=markup)

    # ==============================
    # 🔹 PAGO GENERAL EN DÓLARES
    # ==============================
    elif data == "pago_dolares_general":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("💳 Pagar ahora", url=BMC_URL)
        )
        bot.send_message(chat_id, "💳 Paga en dólares con tarjeta:", reply_markup=markup)

    # ==============================
    # 🔹 SELECCIÓN DE PLAN
    # Ej: plan_copper_soles
    # ==============================
    elif data.startswith("plan_"):
        partes = data.split("_")

        if len(partes) >= 3:
            plan = partes[1]
            moneda = partes[2]

            if moneda == "soles":
                user_states[user_id] = {
                    "estado": "esperando_voucher",
                    "plan": plan
                }

                bot.send_message(
                    chat_id,
                    f"📸 Envía el voucher del plan *{plan.upper()}*.",
                    parse_mode="Markdown"
                )

            elif moneda == "dolares":
                link = BMC_LINKS.get(plan)

                if link:
                    markup = InlineKeyboardMarkup()
                    markup.add(
                        InlineKeyboardButton(
                            "💳 Pagar ahora",
                            url=f"{link}?ref={user_id}"
                        )
                    )

                    bot.send_message(
                        chat_id,
                        f"💳 Has elegido *{plan.upper()}* en dólares.",
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )

    # ==============================
    # 🔹 CANCELAR VOUCHER
    # ==============================
    elif data == "cancelar_voucher":
        if user_id in user_states:
            del user_states[user_id]

            supabase_service.table('pagos_manuales') \
                .update({"estado": "cancelado"}) \
                .eq("usuario_id", user_id) \
                .eq("estado", "pendiente") \
                .execute()

            bot.send_message(chat_id, "✅ Pago cancelado.")

    else:
        bot.send_message(chat_id, "⚠️ Opción no reconocida.")


#// FOTO (Voucher + Soporte)

@bot.message_handler(content_types=['photo'])
def recibir_foto(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id in user_states and user_states[user_id]["estado"] == "esperando_voucher":
        plan = user_states[user_id]["plan"]

        bot.send_message(
            chat_id,
            f"✅ ¡Voucher recibido! Tu pago de *{plan.upper()}* será revisado, si es correcto se te enviaran 2 enlaces a los canales privados y se te activara tu Membresía",
            parse_mode="Markdown"
        )

        bot.send_photo(
            GRUPO_SOPORTE_ID,
            message.photo[-1].file_id,
            caption=f"📸 VOUCHER\nUsuario: {user_id}\nPlan: {plan.upper()}"
        )

        del user_states[user_id]
        return

    bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    bot.send_message(chat_id, "📩 Tu imagen fue enviada a soporte.")

#// ARCHIVOS (video, doc, audio, voz)

@bot.message_handler(content_types=['video', 'document', 'audio', 'voice'])
def soporte_archivos(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id in user_states:
        return

    bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    bot.send_message(chat_id, "📩 Tu archivo fue enviado a soporte.")

#//responder desde el grupo

@bot.message_handler(func=lambda m: m.chat.id == GRUPO_SOPORTE_ID and m.reply_to_message)
def responder_desde_grupo(message):
    try:
        mensaje_original = message.reply_to_message

        # Verificar que sea un mensaje reenviado
        if mensaje_original.forward_from:
            user_id = mensaje_original.forward_from.id

            if message.text:
                bot.send_message(
                    user_id,
                    f"📝 *Respuesta de soporte:*\n\n{message.text}",
                    parse_mode="Markdown"
                )

            elif message.photo:
                bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=f"📝 Respuesta de soporte:\n\n{message.caption or ''}"
                )

            elif message.document:
                bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=f"📝 Respuesta de soporte:\n\n{message.caption or ''}"
                )

            elif message.video:
                bot.send_video(
                    user_id,
                    message.video.file_id,
                    caption=f"📝 Respuesta de soporte:\n\n{message.caption or ''}"
                )

            bot.reply_to(message, "✅ Respuesta enviada al usuario.")

        else:
            bot.reply_to(message, "❌ Este mensaje no es un forward válido.")

    except Exception as e:
        print("Error respondiendo desde grupo:", e)
        bot.reply_to(message, "❌ Error al enviar respuesta.")

#// ÚNICO HANDLER DE TEXTO

@bot.message_handler(content_types=['text'])
def manejar_texto(message):

    # 🚫 Ignorar mensajes del grupo soporte
    if message.chat.id == GRUPO_SOPORTE_ID:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    text_original = message.text.strip()
    text = text_original.lower()

    botones = [
        "💎 Ver Planes",
        "🎬 Beneficios VIP",
        "🇵🇪 Pago en Soles",
        "💳 Pago en Dólares",
        "👤 Mi Perfil",
        "🆘 Ayuda"
    ]

    # Ignorar comandos y botones
    if text_original.startswith("/") or text_original in botones:
         return
    # ==============================
    # SI ESTÁ ESPERANDO VOUCHER
    # ==============================
    if user_id in user_states and user_states[user_id]["estado"] == "esperando_voucher":
        bot.send_message(
            chat_id,
            "❌ Envía una FOTO del voucher o presiona Cancelar."
        )
        return
           # ==============================
    # 🔹 SOLICITUD DIRECTA DE HUMANO / ADMIN
    # ==============================
    if any(palabra in text for palabra in ["humano", "admin", "persona", "real"]):

        bot.send_message(
            chat_id,
            "👨‍💼 Claro, te pondré en contacto con un administrador.\n\n"
            "📩 Tu mensaje fue enviado directamente al equipo.\n"
            "🕒 Te responderemos lo antes posible."
        )

        # También reenviamos el mensaje original
        bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)

        return

    # ==============================
    # PALABRAS CLAVE
    # ==============================
    for keyword, reply in KEYWORD_REPLIES.items():
        if keyword in text:
            bot.send_message(chat_id, reply, parse_mode="Markdown")
            return

    # ==============================
    # SI NO COINCIDE → SOPORTE
    # ==============================
    bot.forward_message(GRUPO_SOPORTE_ID, chat_id, message.message_id)
    bot.send_message(chat_id, "📩 Tu mensaje fue enviado a soporte.")

# ============ SISTEMA DE RESPUESTAS AUTOMÁTICAS (KEYWORD REPLIES) ============
KEYWORD_REPLIES = {
    # Saludos y presentación
    "hola": "👋 ¡Hola! Bienvenido a QuehayApp VIP. ¿Te gustaría conocer nuestros planes?",
    "buenos días": "¡Buenos días! ⭐ ¿En qué puedo ayudarte hoy?",
    "buenas tardes": "¡Buenas tardes! ¿Necesitas información sobre las membresías?",
    "buenas noches": "¡Buenas noches! Aunque sea tarde, siempre estamos para servirte.",

    # Consultas sobre planes
    "planes": (
    "💎✨ *PLANES VIP DISPONIBLES* ✨💎\n\n"
    "🥉 *COPPER* — S/22 | $5.99\n"
    "🔓 Acceso a canales (sin pedidos)\n\n"
    "🥈 *SILVER* — S/33 | $8.99\n"
    "📦 2 pedidos por mes\n\n"
    "🥇 *GOLD* — S/85 | $22.99\n"
    "🎬 3 pedidos cada 3 meses\n\n"
    "🏆 *PLATINUM* — S/163 | $43.99\n"
    "🚀 5 pedidos cada 6 meses\n\n"
    "💠 *DIAMOND* — S/348 | $93.99\n"
    "👑 8 pedidos al año\n\n"
    "💳 ¿Te gustaría pagar en *soles* o en *dólares*?"
    ),
    "bro":  (
    "😎 ¡Habla bro! ¿Qué necesitas hoy?\n\n"
    "💎 Escribe *planes* para ver membresías\n"
    "💳 Escribe *comprar* para activar tu acceso\n"
    "🆘 Escribe *ayuda* si tienes un problema"
    ),
    "precio": (
        "💰 *Precios actualizados*\n\n"
        "🥉 COPPER: S/22 / $5.99 · 🥈 SILVER: S/33 / $8.99 · 🥇 GOLD: S/85 / $22.99 · "
        "🏆 PLATINUM: S/163 / $43.99 ·💠 DIAMOND: S/348 / $93.99"
    ),
    "membresía": "Para ver nuestras membresías, escribe 'planes' o haz clic en el botón '💎 Ver Planes'.",
    "costo": "Los costos están en soles y dólares. Escribí 'planes' para ver el detalle.",

    # Intención de compra
    "comprar": (
        "🛒 *¡Genial! Elige tu método de pago:*\n\n"
        "🇵🇪 *Yape/Plin* (pago en soles)\n"
        "💳 *Tarjeta internacional* (dólares, vía Buy Me a Coffee)\n\n"
        "¿Cuál prefieres?"
    ),
    "quiero comprar": "Perfecto. Primero, ¿quieres pagar en soles o en dólares?",
    "yape": (
        "🇵🇪 *Pago con Yape/Plin*\n\n"
        "1. Abre la mini app y selecciona el plan que deseas.\n"
        "2. Presiona '🇵🇪 Yape / Plin'.\n"
        "3. Sigue las instrucciones y envía el voucher.\n\n"
        "¿Ya tienes la mini app abierta?"
    ),
    "plin": "El proceso es el mismo que con Yape. Usa la mini app para generar el pedido de pago.",
    "tarjeta": (
        "💳 *Pago con tarjeta internacional*\n\n"
        "1. Elige el plan en la mini app.\n"
        "2. Presiona '💳 Tarjeta Gpay ApplePay y mas'.\n"
        "3. Serás redirigido a Buy Me a Coffee para completar el pago.\n"
        "4. Al finalizar, tu membresía se activará automáticamente.\n\n"
        "¿Listo para continuar?"
    ),

    # Beneficios
    "beneficios": (
    "✨🎬 *BENEFICIOS DE SER VIP* 🎬✨\n\n"
    "🔐 *Ingreso VIP al canal privado de Telegram*\n"
    "📥 Ver y descargar directamente en Telegram\n"
    "🔗 Enlaces directos sin complicaciones\n"
    "🚫 Libre de publicidad\n"
    "🎞 Contenido exclusivo actualizado\n"
    "📺 Incluye series completas\n"
    "📦 Incluye pedidos en algunos planes\n"
    "🤖 Bot asistente inteligente\n"
    "📲 MiniApp integrada en Telegram\n"
    "🛟 Soporte básico y avanzado\n\n"
    "💎 ¿Te gustaría ver los planes disponibles?"
     ),
    "que incluye": "Los beneficios incluyen acceso a canales privados y la posibilidad de pedir películas. Escribe 'beneficios' para más detalles.",

    # Soporte y ayuda
    "ayuda": (
        "🆘 *¿Necesitas ayuda?*\n\n"
        "• Para ver planes, escribe 'planes'\n"
        "• Para comprar, escribe 'comprar'\n"
        "• Para problemas con pagos, escribe 'soporte'\n"
        "• Para contactar a un humano, describe tu problema y te responderemos."
    ),
    "soporte": (
        "📞 *Contacta con soporte*\n\n"
        "Cuéntanos tu problema con el mayor detalle posible:\n"
        "- ID de Telegram (lo ves en tu perfil de la mini app)\n"
        "- Tipo de problema (pago, acceso, pedidos, etc.)\n"
        "- Captura de pantalla si es necesario.\n\n"
        "Un administrador te responderá a la brevedad."
    ),
    "problema": "Lamento el inconveniente. Por favor, explícanos qué sucede para poder ayudarte.",
    "error": "Parece que algo no funcionó. ¿Puedes darnos más detalles?",

    # Pedidos
    "pedido": (
        "📦 *Solicitar película/serie*\n\n"
        "1. Debes tener una membresía activa (Silver o superior).\n"
        "2. Abre la mini app y ve a 'Pedidos'.\n"
        "3. Completa el formulario con el título y tipo.\n\n"
        "¿Tienes membresía activa?"
    ),
    "mis pedidos": "Puedes ver el estado de tus pedidos en la mini app, sección 'Pedidos'. Allí aparecen los que has solicitado.",

    # Enlaces y acceso
    "enlace": (
        "🔗 *Acceso a los canales*\n\n"
        "Si ya tienes una membresía activa, los enlaces de acceso se te enviaron automáticamente al activarla.\n"
        "Si no los recibiste, escribe 'no me llegaron los enlaces'."
    ),
    "no me llegaron los enlaces": "Revisaremos tu caso. Por favor, indícanos tu ID de Telegram (lo encuentras en el perfil de la mini app) para que un admin te ayude.",

    # Agradecimientos y despedida
    "gracias": "😊 ¡A ti por confiar en nosotros! Disfruta del contenido.",
    "chau": "👋 ¡Hasta pronto! Vuelve cuando quieras a ver más películas."
}

# ============ FUNCIÓN DE ACTIVACIÓN REUTILIZABLE ============
def activar_usuario(user_id, membresia, chat_id_admin):
    try:
        plan_result = supabase_service.table('membresias_planes').select('*').eq('nombre', membresia).execute()
        if not plan_result.data:
            bot.send_message(chat_id_admin, "❌ Membresía no válida")
            return False

        plan_data = plan_result.data[0]
        duracion_plan = plan_data['duracion_dias']
        limite_pedidos_nuevo = plan_data['pedidos_por_mes']

        es_mejora = False
        dias_extra = 0
        pedidos_extra = 0
        plan_anterior_nombre = None

        usuario_actual = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
        tiene_membresia_activa = usuario_actual.data and usuario_actual.data[0].get('membresia_activa')

        if tiene_membresia_activa:
            usuario = usuario_actual.data[0]
            fecha_vencimiento_actual = datetime.fromisoformat(usuario['fecha_vencimiento'])
            dias_restantes = (fecha_vencimiento_actual - datetime.now()).days
            if dias_restantes > 0:
                es_mejora = True
                dias_extra = dias_restantes
                plan_anterior_nombre = usuario.get('membresia_tipo', 'anterior')

                mem_ant = supabase_service.table('membresias_activas') \
                    .select('fecha_inicio, plan_id') \
                    .eq('usuario_id', usuario['id']) \
                    .eq('estado', 'activa') \
                    .execute()
                if mem_ant.data:
                    fecha_inicio_ant = datetime.fromisoformat(mem_ant.data[0]['fecha_inicio'])
                    pedidos_usados = supabase_service.table('pedidos') \
                        .select('*', count='exact') \
                        .eq('usuario_id', user_id) \
                        .gte('fecha_pedido', fecha_inicio_ant.isoformat()) \
                        .lte('fecha_pedido', datetime.now().isoformat()) \
                        .execute()
                    usados = pedidos_usados.count if hasattr(pedidos_usados, 'count') else len(pedidos_usados.data)

                    plan_ant = supabase_service.table('membresias_planes').select('pedidos_por_mes').eq('id', mem_ant.data[0]['plan_id']).execute()
                    limite_anterior = plan_ant.data[0]['pedidos_por_mes'] if plan_ant.data else 0
                    pedidos_extra = max(0, limite_anterior - usados)

        fecha_vencimiento = datetime.now() + timedelta(days=duracion_plan + dias_extra)

        if not usuario_actual.data:
            nombre = f"Usuario_{user_id}"
        else:
            nombre = usuario_actual.data[0].get('nombre', f"Usuario_{user_id}")

        usuario_data = {
            "telegram_id": user_id,
            "nombre": nombre,
            "membresia_tipo": membresia,
            "membresia_activa": True,
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "pedidos_mes": 0
        }
        supabase_service.table('usuarios').upsert(usuario_data, on_conflict='telegram_id').execute()

        usuario_id = supabase_service.table('usuarios').select('id').eq('telegram_id', user_id).execute().data[0]['id']

        supabase_service.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', usuario_id).eq('estado', 'activa').execute()

        supabase_service.table('membresias_activas').insert({
            "usuario_id": usuario_id,
            "plan_id": plan_data['id'],
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": fecha_vencimiento.isoformat(),
            "estado": "activa",
            "metodo_pago": "auto",
            "monto": plan_data['precio_soles'],
            "pedidos_extra": pedidos_extra
        }).execute()

        if not tiene_membresia_activa:
            try:
                invite_link_pelis = bot.create_chat_invite_link(
                    chat_id=CANAL_PELICULAS_ID,
                    name=f"Usuario_{user_id}_pelis",
                    member_limit=1,
                    expire_date=int(time.time()) + 604800
                )
                invite_link_series = bot.create_chat_invite_link(
                    chat_id=CANAL_SERIES_ID,
                    name=f"Usuario_{user_id}_series",
                    member_limit=1,
                    expire_date=int(time.time()) + 604800
                )
                bot.send_message(
                    user_id,
                    f"🔐 *ACCESO A TUS CANALES*\n\n"
                    f"🎬 *CANAL DE PELÍCULAS:*\n{invite_link_pelis.invite_link}\n\n"
                    f"📺 *CANAL DE SERIES:*\n{invite_link_series.invite_link}\n\n"
                    f"⚠️ Enlaces de USO ÚNICO - Expiran en 7 días",
                )
                bot.send_message(chat_id_admin, f"✅ Usuario {user_id} activado y enlaces enviados")
            except Exception as e:
                bot.send_message(chat_id_admin, f"⚠️ Membresía activada pero error con enlaces: {e}")
                bot.send_message(user_id, f"🎉 Membresía activada. En breve recibirás los enlaces.")
        else:
            bot.send_message(chat_id_admin, f"✅ Usuario {user_id} mejoró a {membresia} (sin nuevos enlaces)")

        total_pedidos = limite_pedidos_nuevo + pedidos_extra
        if es_mejora:
            mensaje = (
                f"🔄 *¡Mejoraste a {membresia.upper()}!*\n\n"
                f"Hemos sumado los {dias_extra} días que te quedaban de tu plan {plan_anterior_nombre.capitalize()} "
                f"y tus {pedidos_extra} pedidos no usados a tu nueva membresía.\n"
                f"📅 *Nueva fecha de vencimiento:* {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"🎟 *Pedidos disponibles en tu membresía actual:* {total_pedidos}\n\n"
                f"¡Gracias por confiar en nosotros!"
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

# ============ COMANDOS DE ACTIVACIÓN ============
@bot.message_handler(commands=['activar'])
def activar(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        partes = message.text.split()
        if len(partes) < 3:
            bot.reply_to(message, "❌ Usa: /activar USER_ID PLAN")
            return

        user_id = int(partes[1])
        membresia = partes[2].lower()

        activar_usuario(user_id, membresia, message.chat.id)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['auto_activar'])
def auto_activar(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        partes = message.text.split()
        if len(partes) < 3:
            bot.reply_to(message, "❌ Usa: /auto_activar USER_ID PLAN")
            return

        user_id = int(partes[1])
        membresia = partes[2].lower()

        activar_usuario(user_id, membresia, message.chat.id)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ============ OTROS COMANDOS ADMIN ============
@bot.message_handler(commands=['activos'])
def listar_activos(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        usuarios_activos = supabase_service.table('usuarios') \
            .select('telegram_id, nombre, membresia_tipo, fecha_vencimiento') \
            .eq('membresia_activa', True) \
            .execute()
        
        if not usuarios_activos.data or len(usuarios_activos.data) == 0:
            bot.send_message(message.chat.id, "📭 No hay usuarios con membresía activa")
            return
        
        mensaje = "📋 USUARIOS CON MEMBRESÍA ACTIVA:\n\n"
        
        for u in usuarios_activos.data:
            vence = u.get('fecha_vencimiento', '')[:10] if u.get('fecha_vencimiento') else 'Sin fecha'
            mensaje += f"👤 ID: {u['telegram_id']}\n"
            mensaje += f"👤 Nombre: {u.get('nombre', 'N/A')}\n"
            mensaje += f"💎 Plan: {u.get('membresia_tipo', 'N/A')}\n"
            mensaje += f"📅 Vence: {vence}\n"
            mensaje += "───────────────\n"
        
        mensaje += f"\n📊 Total: {len(usuarios_activos.data)} usuarios"
        bot.send_message(message.chat.id, mensaje)
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['desactivar'])
def desactivar(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.send_message(message.chat.id, "❌ Usa: /desactivar ID_USUARIO")
            return
            
        user_id = int(partes[1])
        usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
        
        if not usuario.data:
            bot.send_message(message.chat.id, f"❌ Usuario {user_id} no encontrado")
            return
            
        usuario_data = usuario.data[0]
        usuario_id = usuario_data['id']
        
        supabase_service.table('usuarios').update({"membresia_activa": False}).eq('telegram_id', user_id).execute()
        supabase_service.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', usuario_id).eq('estado', 'activa').execute()
        
        bot.send_message(message.chat.id, f"✅ Usuario {user_id} desactivado")
        
        try:
            bot.send_message(user_id, "⚠️ Tu membresía ha sido desactivada.")
        except:
            pass
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['generar_enlaces'])
def generar_enlaces(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 3:
            bot.reply_to(message, "❌ Usa: /generar_enlaces USER_ID PLAN")
            return
            
        user_id = int(partes[1])
        membresia = partes[2]
        
        # Verificar que el usuario existe
        usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
        if not usuario.data:
            bot.reply_to(message, f"❌ Usuario {user_id} no encontrado")
            return
        
        # Generar enlaces
        invite_link_pelis = bot.create_chat_invite_link(
            chat_id=CANAL_PELICULAS_ID,
            name=f"Usuario_{user_id}_pelis",
            member_limit=1,
            expire_date=int(time.time()) + 604800
        )
        
        invite_link_series = bot.create_chat_invite_link(
            chat_id=CANAL_SERIES_ID,
            name=f"Usuario_{user_id}_series",
            member_limit=1,
            expire_date=int(time.time()) + 604800
        )
        
        # Enviar al usuario (SIN MARKDOWN)
        bot.send_message(
            user_id,
            f"🔐 ACCESO A TUS CANALES\n\n"
            f"🎬 CANAL DE PELÍCULAS:\n{invite_link_pelis.invite_link}\n\n"
            f"📺 CANAL DE SERIES:\n{invite_link_series.invite_link}\n\n"
            f"⚠️ Enlaces de USO ÚNICO - Expiran en 7 días"
            # 👈 SIN parse_mode
        )
        
        bot.reply_to(message, f"✅ Enlaces enviados a {user_id}")
        
        # Guardar en base de datos (opcional)
        try:
            supabase_service.table('invitaciones').insert([
                {
                    "usuario_id": user_id,
                    "canal": "peliculas",
                    "enlace": invite_link_pelis.invite_link,
                    "expira": (datetime.now() + timedelta(days=7)).isoformat(),
                    "usado": False
                },
                {
                    "usuario_id": user_id,
                    "canal": "series",
                    "enlace": invite_link_series.invite_link,
                    "expira": (datetime.now() + timedelta(days=7)).isoformat(),
                    "usado": False
                }
            ]).execute()
        except Exception as e:
            print(f"⚠️ No se pudo guardar en invitaciones: {e}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
    
@bot.message_handler(commands=['reactivar'])
def reactivar(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        partes = message.text.split()
        if len(partes) < 3:
            bot.send_message(message.chat.id, "❌ Usa: /reactivar ID_USUARIO PLAN")
            return
            
        user_id = int(partes[1])
        membresia = partes[2].lower()
        
        activar_usuario(user_id, membresia, message.chat.id)
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def debug_all(message):
    print("📩 DEBUG GLOBAL:", message.chat.id, message.text)
@bot.message_handler(commands=['id'])
def get_id(message):
    bot.reply_to(message, f"Chat ID: {message.chat.id}")


# ============ WEBHOOK PARA RENDER ============

from flask import Flask, request

app = Flask(__name__)
CORS(app)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

from flask import jsonify

@app.route("/aprobar_pago", methods=["POST"])
def aprobar_pago():
    try:
        data = request.get_json()
        pago_id = data.get("pagoId")

        if not pago_id:
            return jsonify({"error": "pagoId requerido"}), 400

        # 1️⃣ Obtener pago
        pago_res = supabase_service.table("pagos_manuales").select("*").eq("id", pago_id).execute()
        if not pago_res.data:
            return jsonify({"error": "Pago no encontrado"}), 404

        pago = pago_res.data[0]

        # 2️⃣ Obtener usuario
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", pago["usuario_id"]).execute()
        if not usuario_res.data:
            return jsonify({"error": "Usuario no encontrado"}), 404

        usuario = usuario_res.data[0]

        # 3️⃣ Activar membresía usando tu función existente
        activado = activar_usuario(
            pago["usuario_id"],
            pago["membresia_comprada"].lower(),
            ADMIN_ID
        )

        if not activado:
            return jsonify({"error": "Error activando membresía"}), 500

        # 4️⃣ Marcar pago como aprobado
        supabase_service.table("pagos_manuales").update({
            "estado": "aprobado",
            "activado": True
        }).eq("id", pago_id).execute()

        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ ERROR aprobar_pago:", e)
        return jsonify({"error": str(e)}), 500

from flask import jsonify

def limpiar_membresias_vencidas():
    """Revisa membresías vencidas y actualiza el estado en usuarios."""
    ahora = datetime.now().isoformat()

    # Buscar usuarios con membresía activa pero fecha vencida
    usuarios = supabase_service.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", ahora) \
        .execute()

    for u in usuarios.data:
        # Desactivar membresía en usuarios
        supabase_service.table("usuarios").update({
            "membresia_activa": False
        }).eq("id", u["id"]).execute()

        # Opcional: también podrías desactivar el registro en membresias_activas
        supabase_service.table("membresias_activas").update({
            "estado": "inactiva"
        }).eq("usuario_id", u["id"]).eq("estado", "activa").execute()

        # Notificar al usuario (opcional, pero recomendado)
        try:
            bot.send_message(
                u["telegram_id"],
                "⚠️ Tu membresía ha vencido. Renueva para seguir disfrutando."
            )
        except:
            pass

        print(f"✅ Membresía vencida desactivada para usuario {u['telegram_id']}")

# ============ CREAR PAGO TARJETA ============

@app.route("/crear_pago_tarjeta", methods=["POST"])
def crear_pago_tarjeta():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        plan = data.get("plan")
        email = data.get("email")

        if not telegram_id or not plan or not email:
            return jsonify({"error": "Datos incompletos"}), 400

        # 1️⃣ Guardar email en usuario
        supabase_service.table("usuarios").update({
            "email": email
        }).eq("telegram_id", telegram_id).execute()

        # 2️⃣ Guardar pago pendiente_webhook
        supabase_service.table("pagos_manuales").insert({
            "usuario_id": telegram_id,
            "membresia_comprada": plan.lower(),
            "metodo": "tarjeta",
            "estado": "pendiente_webhook",
            "activado": False,
            "email": email,
            "fecha_pago": datetime.now().isoformat()
        }).execute()

        # 3️⃣ Links BuyMeACoffee
        links = {
            "copper": "https://buymeacoffee.com/quehay/membership",
            "silver": "https://buymeacoffee.com/quehay/membership",
            "gold": "https://buymeacoffee.com/quehay/e/510546",
            "platinum": "https://buymeacoffee.com/quehay/e/510549",
            "diamond": "https://buymeacoffee.com/quehay/e/510552"
        }

        return jsonify({
            "success": True,
            "url": links.get(plan.lower())
        }), 200

    except Exception as e:
        print("❌ Error crear_pago_tarjeta:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/crear_pedido", methods=["POST"])
def crear_pedido():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        titulo = data.get("titulo")
        tipo = data.get("tipo")

        if not telegram_id or not titulo:
            return jsonify({"error": "Datos incompletos"}), 400

        # 1️⃣ Obtener usuario
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
        if not usuario_res.data:
            return jsonify({"error": "Usuario no encontrado"}), 404
        usuario = usuario_res.data[0]

        if not usuario.get("membresia_activa"):
            return jsonify({"error": "No tienes membresía activa"}), 403

        # 2️⃣ Obtener membresía activa (sin join)
        hoy = datetime.now().isoformat()
        mem_res = supabase_service.table("membresias_activas") \
            .select("*") \
            .eq("usuario_id", usuario["id"]) \
            .eq("estado", "activa") \
            .gte("fecha_fin", hoy) \
            .execute()
        if not mem_res.data:
            return jsonify({"error": "No se encontró membresía activa válida"}), 403
        membresia = mem_res.data[0]

        # 3️⃣ Obtener el plan por separado
        plan_res = supabase_service.table("membresias_planes") \
            .select("*") \
            .eq("id", membresia["plan_id"]) \
            .execute()
        if not plan_res.data:
            return jsonify({"error": "Plan no encontrado"}), 404
        plan = plan_res.data[0]

        # 4️⃣ Validar límite de pedidos
        pedidos_extra = membresia.get("pedidos_extra", 0)
        limite_total = plan["pedidos_por_mes"] + pedidos_extra

        if limite_total == 0:
            return jsonify({"error": "Tu plan no incluye pedidos"}), 403

        # 5️⃣ Contar pedidos usados en el período
        pedidos_usados_res = supabase_service.table("pedidos") \
            .select("*", count="exact") \
            .eq("usuario_id", telegram_id) \
            .gte("fecha_pedido", membresia["fecha_inicio"]) \
            .lte("fecha_pedido", hoy) \
            .execute()
        usados = pedidos_usados_res.count if hasattr(pedidos_usados_res, 'count') else len(pedidos_usados_res.data)

        if usados >= limite_total:
            return jsonify({"error": "Has alcanzado el límite de tu plan"}), 403

        # 6️⃣ Insertar pedido
        supabase_service.table("pedidos").insert({
            "usuario_id": telegram_id,
            "titulo_pedido": titulo,
            "tipo": tipo,
            "estado": "pendiente",
            "fecha_pedido": datetime.now().isoformat()
        }).execute()

        restantes = limite_total - (usados + 1)

        # 7️⃣ Notificaciones
        bot.send_message(
            ADMIN_ID,
            f"📥 NUEVO PEDIDO\n\n"
            f"👤 Usuario: {telegram_id}\n"
            f"🎬 Título: {titulo}\n"
            f"📦 Plan: {plan['nombre']}\n"
            f"📊 Restantes: {restantes}"
        )
        bot.send_message(
            telegram_id,
            f"✅ Pedido enviado correctamente.\n\n"
            f"📦 Te quedan {restantes} pedidos disponibles."
        )

        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ ERROR crear_pedido:", str(e))
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@app.route("/admin_pedidos", methods=["POST", "OPTIONS"])
def admin_pedidos():
    # Manejar preflight CORS
    if request.method == "OPTIONS":
        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response, 200

    try:
        data = request.get_json()
        admin_id = data.get("admin_id")

        # Verificar que es el admin
        if admin_id != ADMIN_ID:
            response = jsonify({"error": "No autorizado"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 403

        # Obtener TODOS los pedidos con información del usuario
        pedidos_res = supabase_service.table("pedidos") \
            .select("*, usuarios!inner(*)") \
            .order("fecha_pedido", desc=True) \
            .execute()

        pedidos = []
        for p in pedidos_res.data:
            pedidos.append({
                "id": p["id"],
                "pedido_id": p["id"],
                "titulo": p["titulo_pedido"],
                "tipo": p.get("tipo", "pelicula"),
                "estado": p["estado"],
                "fecha": datetime.fromisoformat(p["fecha_pedido"]).strftime("%d/%m/%Y %H:%M"),
                "usuario": {
                    "telegram_id": p["usuarios"]["telegram_id"],
                    "nombre": p["usuarios"].get("nombre", "Desconocido"),
                    "membresia": p["usuarios"].get("membresia_tipo", "Ninguna")
                }
            })

        response = jsonify({
            "pedidos": pedidos,
            "total": len(pedidos),
            "pendientes": len([p for p in pedidos if p["estado"] == "pendiente"])
        })
        
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200

    except Exception as e:
        print("❌ ERROR en admin_pedidos:", e)
        response = jsonify({"error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

#  IMPORTANTE: Este decorador NO debe estar indentado
@app.route("/marcar_entregado", methods=["POST", "OPTIONS"])
def marcar_entregado():
    # Manejar preflight CORS
    if request.method == "OPTIONS":
        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response, 200

    try:
        data = request.get_json()
        pedido_id = data.get("pedido_id")
        admin_id = data.get("admin_id")

        # Verificar que es el admin
        if admin_id != ADMIN_ID:
            response = jsonify({"error": "No autorizado"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 403

        # Obtener pedido con información del usuario
        pedido_res = supabase_service.table("pedidos") \
            .select("*, usuarios!inner(*)") \
            .eq("id", pedido_id) \
            .execute()

        if not pedido_res.data:
            response = jsonify({"error": "Pedido no encontrado"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404

        pedido = pedido_res.data[0]

        # Actualizar estado del pedido
        supabase_service.table("pedidos").update({
            "estado": "entregado",
            "fecha_respuesta": datetime.now().isoformat()
        }).eq("id", pedido_id).execute()

        telegram_id = pedido["usuarios"]["telegram_id"]

        # Notificar al usuario
        try:
            bot.send_message(
                telegram_id,
                f"✅ ¡Tu pedido ya está disponible!\n\n"
                f"🎬 *{pedido['titulo_pedido']}*\n\n"
                f"Ya puedes verlo en los canales.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"⚠️ No se pudo notificar al usuario: {e}")

        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200

    except Exception as e:
        print("❌ ERROR en marcar_entregado:", e)
        response = jsonify({"error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@app.route("/mis_pedidos", methods=["POST", "OPTIONS"])
def mis_pedidos():
    # Manejar preflight CORS
    if request.method == "OPTIONS":
        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response, 200

    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")

        if not telegram_id:
            return jsonify({"error": "telegram_id requerido"}), 400

        # Buscar pedidos del usuario
        pedidos_res = supabase_service.table("pedidos") \
            .select("*") \
            .eq("usuario_id", telegram_id) \
            .order("fecha_pedido", desc=True) \
            .execute()

        # Formatear pedidos para la respuesta
        pedidos = []
        for p in pedidos_res.data:
            pedidos.append({
                "id": p["id"],
                "titulo": p["titulo_pedido"],
                "tipo": p.get("tipo", "pelicula"),
                "estado": p["estado"],
                "fecha": datetime.fromisoformat(p["fecha_pedido"]).strftime("%d/%m/%Y %H:%M")
            })

        # También obtener info del usuario para mostrar membresía
        usuario_res = supabase_service.table("usuarios") \
            .select("membresia_tipo, membresia_activa") \
            .eq("telegram_id", telegram_id) \
            .execute()

        response = jsonify({
            "pedidos": pedidos,
            "total": len(pedidos),
            "usuario": usuario_res.data[0] if usuario_res.data else None
        })
        
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 200

    except Exception as e:
        print("❌ ERROR en mis_pedidos:", e)
        response = jsonify({"error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

# ============ ENDPOINT PARA CRON-JOB (VERIFICAR VENCIMIENTOS) ============
@app.route("/cron/verificar_vencimientos", methods=["GET"])
def cron_verificar_vencimientos():
    """Endpoint para ser llamado por cron-job.org periódicamente."""
    try:
        verificar_vencimientos()  # ← Esta función la definiremos abajo
        return "OK", 200
    except Exception as e:
        print(f"Error en cron: {e}")
        return "Error", 500
    
def verificar_vencimientos():
    """Ejecutar periódicamente para notificar y expulsar."""
    ahora = datetime.now()
    hoy = ahora.isoformat()

    # --- 1. Usuarios que vencen en 3 días ---
    en_3_dias = (ahora + timedelta(days=3)).isoformat()
    usuarios_proximos = supabase_service.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3_dias) \
        .execute()

    for u in usuarios_proximos.data:
        try:
            vence = datetime.fromisoformat(u["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
            bot.send_message(
                u["telegram_id"],
                f"⏳ *Tu membresía vence en 3 días* ({vence}).\n"
                f"Renueva para no perder el acceso.",
                parse_mode="Markdown"
            )
            print(f"Notificación 3 días enviada a {u['telegram_id']}")
        except Exception as e:
            print(f"Error notificando a {u['telegram_id']}: {e}")

    # --- 2. Usuarios que vencen en 3 horas ---
    en_3_horas = (ahora + timedelta(hours=3)).isoformat()
    usuarios_muy_proximos = supabase_service.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3_horas) \
        .execute()

    for u in usuarios_muy_proximos.data:
        try:
            vence = datetime.fromisoformat(u["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
            bot.send_message(
                u["telegram_id"],
                f"⚠️ *¡Tu membresía vence en 3 horas!* ({vence}).\n"
                f"Renueva para mantener el acceso.",
                parse_mode="Markdown"
            )
            print(f"Notificación 3 horas enviada a {u['telegram_id']}")
        except Exception as e:
            print(f"Error notificando a {u['telegram_id']}: {e}")

    # --- 3. Usuarios ya vencidos (limpiar y expulsar) ---
    usuarios_vencidos = supabase_service.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", hoy) \
        .execute()

    for u in usuarios_vencidos.data:
        # Desactivar en BD
        supabase_service.table("usuarios").update({"membresia_activa": False}).eq("id", u["id"]).execute()
        supabase_service.table("membresias_activas").update({"estado": "inactiva"}).eq("usuario_id", u["id"]).eq("estado", "activa").execute()

        # Expulsar de canales
        try:
            bot.ban_chat_member(chat_id=CANAL_PELICULAS_ID, user_id=u["telegram_id"])
            bot.ban_chat_member(chat_id=CANAL_SERIES_ID, user_id=u["telegram_id"])
            print(f"Usuario {u['telegram_id']} expulsado de canales por vencimiento")
        except Exception as e:
            print(f"Error expulsando a {u['telegram_id']}: {e}")

        # Notificar
        try:
            bot.send_message(
                u["telegram_id"],
                "❌ Tu membresía ha vencido. Has sido expulsado de los canales.\n"
                "Renueva para seguir disfrutando."
            )
        except:
            pass

@app.route("/webhook/buymeacoffee", methods=["POST"])
def webhook_buymeacoffee():
    try:
        data = request.get_json()
        print("📩 Webhook recibido:", data)

        tipo_evento = data.get("type")
        datos = data.get("data", {})

        # 🔹 Extraer email del comprador
        email = datos.get("supporter_email")

        if not email:
            print("❌ No se encontró supporter_email")
            return jsonify({"error": "Email no encontrado"}), 400

        # 🔹 Buscar pago pendiente_webhook por email
        pago_res = supabase_service.table("pagos_manuales") \
            .select("*") \
            .eq("email", email) \
            .eq("estado", "pendiente_webhook") \
            .execute()

        if not pago_res.data:
            print("⚠️ No hay pago pendiente para este email")
            return jsonify({"error": "No hay pago pendiente"}), 400

        registro_pago = pago_res.data[0]
        telegram_id = registro_pago["usuario_id"]
        plan_comprado = registro_pago["membresia_comprada"].lower()

        # 🔹 Determinar si el evento realmente es pago exitoso

        plan_detectado = None

        # ---- MEMBERSHIP (Copper / Silver) ----
        if tipo_evento in ["membership.started", "membership.updated"]:
            estado = datos.get("estado") or datos.get("status")
            cancelado = datos.get("cancelado") or datos.get("canceled")
            cancel_at_period_end = datos.get("cancel_at_period_end") == "true"

            if estado == "active" and not cancelado and not cancel_at_period_end:
                nivel = (datos.get("membership_level_name", "")).lower()
                plan_detectado = nivel

        # ---- EXTRAS (Gold / Platinum / Diamond) ----
        elif tipo_evento == "extra_purchase.created":
            extras = datos.get("extras", [])
            if extras:
                product_id = str(extras[0].get("id"))

                product_to_plan = {
                    "510546": "gold",
                    "510549": "platinum",
                    "510552": "diamond"
                }

                plan_detectado = product_to_plan.get(product_id)

        # ---- CANCELACIONES ----
        elif tipo_evento == "membership.cancelled":
            print("ℹ️ Cancelación recibida, ignorada")
            return jsonify({"success": True}), 200

        else:
            print(f"ℹ️ Evento ignorado: {tipo_evento}")
            return jsonify({"success": True}), 200

        # 🔹 Validar que el plan detectado coincide con el pendiente
        if not plan_detectado or plan_detectado != plan_comprado:
            print("❌ Plan no coincide o no detectado")
            return jsonify({"error": "Plan no coincide"}), 400

        # 🔹 Activar membresía
        exito = activar_usuario(telegram_id, plan_comprado, ADMIN_ID)

        if not exito:
            return jsonify({"error": "Error activando membresía"}), 500

        # 🔹 Marcar pago como aprobado
        supabase_service.table("pagos_manuales").update({
            "estado": "aprobado",
            "activado": True
        }).eq("id", registro_pago["id"]).execute()

        print(f"✅ Usuario {telegram_id} activado automáticamente por tarjeta")

        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ ERROR webhook:", str(e))
        return jsonify({"error": str(e)}), 500

# ============ NUEVOS ENDPOINTS PARA PRODUCCIÓN ============

@app.route("/api/usuario", methods=["POST"])
def api_usuario():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        if not telegram_id:
            return jsonify({"error": "telegram_id requerido"}), 400

        # Obtener usuario
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
        usuario = usuario_res.data[0] if usuario_res.data else None

        membresia = None
        if usuario:
            hoy = datetime.now().isoformat()
            # Obtener membresía activa sin join
            mem_res = supabase_service.table("membresias_activas") \
                .select("*") \
                .eq("usuario_id", usuario["id"]) \
                .eq("estado", "activa") \
                .gte("fecha_fin", hoy) \
                .execute()
            
            if mem_res.data:
                membresia = mem_res.data[0]
                # Obtener el plan por separado
                plan_res = supabase_service.table("membresias_planes") \
                    .select("*") \
                    .eq("id", membresia["plan_id"]) \
                    .execute()
                if plan_res.data:
                    membresia["membresias_planes"] = plan_res.data[0]

        return jsonify({
            "usuario": usuario,
            "membresia": membresia
        }), 200

    except Exception as e:
        print("❌ Error en /api/usuario:", str(e))
        return jsonify({"error": "Error interno del servidor"}), 500
    
@app.route("/api/planes", methods=["GET"])
def api_planes():
    planes = supabase_service.table("membresias_planes").select("*").execute()
    return jsonify(planes.data)

@app.route("/api/contenido", methods=["POST"])
def api_contenido():
    data = request.get_json()
    busqueda = data.get("busqueda", "")
    tipo = data.get("tipo", "todo")

    query = supabase_service.table("contenido").select("*")
    if tipo != "todo":
        query = query.eq("tipo", tipo)
    if busqueda:
        query = query.ilike("titulo", f"%{busqueda}%")
    
    resultados = query.limit(20).execute()
    return jsonify(resultados.data)

@app.route("/api/admin/pagos", methods=["POST"])
def api_admin_pagos():
    data = request.get_json()
    admin_id = data.get("admin_id")
    if admin_id != ADMIN_ID:
        return jsonify({"error": "No autorizado"}), 403

    pagos = supabase_service.table("pagos_manuales") \
        .select("*") \
        .eq("estado", "pendiente") \
        .order("created_at", desc=True) \
        .execute()
    return jsonify(pagos.data)

@app.route("/api/admin/usuarios", methods=["POST"])
def api_admin_usuarios():
    data = request.get_json()
    admin_id = data.get("admin_id")
    if admin_id != ADMIN_ID:
        return jsonify({"error": "No autorizado"}), 403

    usuarios = supabase_service.table("usuarios") \
        .select("*") \
        .order("id", desc=True) \
        .execute()
    return jsonify(usuarios.data)

@app.route("/api/mis_pedidos", methods=["POST"])
def api_mis_pedidos():
    data = request.get_json()
    telegram_id = data.get("telegram_id")
    if not telegram_id:
        return jsonify({"error": "telegram_id requerido"}), 400

    pedidos = supabase_service.table("pedidos") \
        .select("*") \
        .eq("usuario_id", telegram_id) \
        .order("fecha_pedido", desc=True) \
        .execute()

    # Formatear fechas
    for p in pedidos.data:
        p["fecha"] = datetime.fromisoformat(p["fecha_pedido"]).strftime("%d/%m/%Y %H:%M")
    
    return jsonify({"pedidos": pedidos.data})

if __name__ == "__main__":
    print("🚀 Bot iniciado con Webhook...")

    bot.remove_webhook()

    bot.set_webhook(
        url=os.getenv("RENDER_EXTERNAL_URL") + f"/{BOT_TOKEN}"
    )

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )