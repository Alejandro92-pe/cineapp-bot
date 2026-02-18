from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from supabase import create_client
from datetime import datetime, timedelta
import time
import hmac
import hashlib

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
# ============ CANALES PRIVADOS ============
CANAL_PELICULAS_ID = -1003890553566
CANAL_SERIES_ID = -1003879512007

# Inicializar
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

# ============ MENÚ PRINCIPAL ============
def menu_principal(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("💎 Ver Planes"))
    markup.row(KeyboardButton("📲 Cómo Comprar"))
    markup.row(KeyboardButton("🎬 Beneficios"))
    markup.row(KeyboardButton("📞 Soporte"))
    
    bot.send_message(
        chat_id,
        "🎬 *Bienvenido a CineApp VIP*\n\n"
        "Accede a películas y series exclusivas directamente desde Telegram.\n\n"
        "Selecciona una opción:",
        reply_markup=markup,
        parse_mode="Markdown"
    )   
# ============ START ============
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    # Verificar si el usuario ya existe
    usuario = supabase_service.table('usuarios').select('*').eq('telegram_id', user_id).execute()
    
    if not usuario.data:
        supabase_service.table('usuarios').insert({
            "telegram_id": user_id,
            "nombre": user_name,
            "membresia_activa": False
        }).execute()
        print(f"✅ Usuario creado: {user_name} ({user_id})")
    else:
        supabase_service.table('usuarios').update({
            "nombre": user_name
        }).eq('telegram_id', user_id).execute()
        print(f"✅ Usuario actualizado: {user_name}")

    # MODO ADMIN
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "🤖 *Modo Admin Activado*\n\nComandos disponibles:\n"
            "/planes\n"
            "/activar ID PLAN\n"
            "/desactivar ID",
            parse_mode="Markdown"
        )
        return

    # USUARIO NORMAL
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("pago_"):
        partes = args[1].split("_")
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

        bot.send_message(
            message.chat.id,
            f"💎 *PLAN {plan.upper()}*\n\n"
            f"💰 *Monto a pagar:* S/{precio}\n\n"
            "📲 *Método:* Yape / Plin\n\n"
            "👤 *Titular:* Richard Quiroz\n"
            "📱 *Número:* 930202820\n\n"
            "📝 *Concepto a colocar:*\n"
            f"{user_id}\n\n"
            "📸 *Después del pago:*\n"
            "Envía aquí la captura del voucher.\n\n"
            "⏳ Tu membresía será activada una vez validemos el pago.",
            parse_mode="Markdown"
        )
        return

    menu_principal(message.chat.id)

# ============ BOTONES ============
@bot.message_handler(func=lambda message: message.text == "💎 Ver Planes")
def ver_planes(message):
    planes = supabase_service.table('membresias_planes').select('*').execute()
    
    texto = "💎 *Planes Disponibles:*\n\n"
    
    for p in planes.data:
        texto += f"🔹 *{p['nombre'].upper()}*\n"
        texto += f"💰 S/{p['precio_soles']} | ${p['precio_dolares']}\n"
        texto += f"⏳ {p['duracion_dias']} días\n"
        texto += f"📦 {p['pedidos_por_mes']} pedidos\n\n"
    
    texto += "📲 Compra desde la MiniApp."
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📲 Cómo Comprar")
def como_comprar(message):
    bot.send_message(
        message.chat.id,
        "📲 *Cómo comprar tu membresía:*\n\n"
        "1️⃣ Entra a la MiniApp.\n"
        "2️⃣ Elige tu plan.\n"
        "3️⃣ Paga con Yape / Plin o Tarjeta.\n"
        "4️⃣ Tu acceso se activa en minutos.\n\n"
        "⚡ Si pagas con Yape, envía el voucher aquí.",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "🎬 Beneficios")
def beneficios(message):
    bot.send_message(
        message.chat.id,
        "🎬 *Beneficios VIP:*\n\n"
        "✅ Acceso al canal privado\n"
        "✅ Ver y descargar en Telegram\n"
        "✅ Sin publicidad\n"
        "✅ Contenido exclusivo\n"
        "✅ Pedidos según tu plan\n"
        "✅ Soporte directo\n",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "📞 Soporte")
def soporte(message):
    bot.send_message(
        message.chat.id,
        "📞 Soporte:\n\n"
        "Si tienes problemas con tu pago o acceso,\n"
        "envíanos un mensaje aquí mismo y te ayudaremos.",
    )

# ============ ADMIN ============
@bot.message_handler(commands=['planes'])
def planes(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    planes = supabase_service.table('membresias_planes').select('*').execute()
    texto = "📋 MEMBRESÍAS DISPONIBLES:\n\n"
    
    for p in planes.data:
        texto += f"{p['nombre'].upper()} - S/{p['precio_soles']} - {p['duracion_dias']} días - {p['pedidos_por_mes']} pedidos\n"
    
    bot.send_message(message.chat.id, texto)

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

@app.route("/crear_pedido", methods=["POST"])
def crear_pedido():
    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        titulo = data.get("titulo")
        tipo = data.get("tipo")

        if not telegram_id or not titulo:
            return jsonify({"error": "Datos incompletos"}), 400

        # Obtener usuario
        usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
        if not usuario_res.data:
            return jsonify({"error": "Usuario no encontrado"}), 404

        usuario = usuario_res.data[0]
        if not usuario.get("membresia_activa"):
            return jsonify({"error": "No tienes membresía activa"}), 403

        # Obtener membresía activa con plan y pedidos_extra
        hoy = datetime.now().isoformat()
        mem_res = supabase_service.table("membresias_activas") \
            .select("*, membresias_planes!membresias_activas_plan_id_fkey(*)") \
            .eq("usuario_id", usuario["id"]) \
            .eq("estado", "activa") \
            .gte("fecha_fin", hoy) \
            .execute()
        if not mem_res.data:
            return jsonify({"error": "No se encontró membresía activa válida"}), 403

        membresia = mem_res.data[0]
        plan = membresia["membresias_planes"]
        pedidos_extra = membresia.get("pedidos_extra", 0)
        limite_total = plan["pedidos_por_mes"] + pedidos_extra

        if limite_total == 0:
            return jsonify({"error": "Tu plan no incluye pedidos"}), 403

        # Contar pedidos usados en el período actual
        pedidos_usados_res = supabase_service.table("pedidos") \
            .select("*", count="exact") \
            .eq("usuario_id", telegram_id) \
            .gte("fecha_pedido", membresia["fecha_inicio"]) \
            .lte("fecha_pedido", hoy) \
            .execute()
        usados = pedidos_usados_res.count if hasattr(pedidos_usados_res, 'count') else len(pedidos_usados_res.data)

        if usados >= limite_total:
            return jsonify({"error": "Has alcanzado el límite de tu plan"}), 403

        # Insertar pedido
        supabase_service.table("pedidos").insert({
            "usuario_id": telegram_id,
            "titulo_pedido": titulo,
            "tipo": tipo,
            "estado": "pendiente",
            "fecha_pedido": datetime.now().isoformat()
        }).execute()

        restantes = limite_total - (usados + 1)

        # Notificaciones
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

    # --- 3. Usuarios ya vencidos (fecha_vencimiento < hoy) ---
    usuarios_vencidos = supabase_service.table("usuarios") \
        .select("*, membresias_activas!inner(*)") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", hoy) \
        .execute()

for u in usuarios_vencidos.data:
    # Obtener la membresía activa (la que está vencida)
    mem_act = supabase_service.table("membresias_activas") \
        .select("*") \
        .eq("usuario_id", u["id"]) \
        .eq("estado", "activa") \
        .single() \
        .execute()

    if mem_act.data and mem_act.data.get("plan_futuro"):
        # Hay un cambio programado: activar el nuevo plan
        nuevo_plan_id = mem_act.data["plan_futuro"]
        plan_nuevo_res = supabase_service.table("membresias_planes").select("nombre").eq("id", nuevo_plan_id).execute()
        if plan_nuevo_res.data:
            nuevo_plan = plan_nuevo_res.data[0]["nombre"]
            # Activar el nuevo plan (la función ya maneja que no envíe enlaces si ya tenía membresía)
            activar_usuario(u["telegram_id"], nuevo_plan, ADMIN_ID)

        # Limpiar el campo plan_futuro (ya se usó)
        supabase_service.table("membresias_activas") \
            .update({"plan_futuro": None}) \
            .eq("id", mem_act.data["id"]) \
            .execute()

        # No desactivamos la membresía actual porque activar_usuario ya la desactivó y creó una nueva
    else:
        # No hay cambio programado: desactivar y expulsar normalmente
        supabase_service.table("usuarios").update({"membresia_activa": False}).eq("id", u["id"]).execute()
        supabase_service.table("membresias_activas").update({"estado": "inactiva"}).eq("usuario_id", u["id"]).eq("estado", "activa").execute()

        # Expulsar de canales
        try:
            bot.ban_chat_member(chat_id=CANAL_PELICULAS_ID, user_id=u["telegram_id"])
            bot.ban_chat_member(chat_id=CANAL_SERIES_ID, user_id=u["telegram_id"])
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
    # ... (código de verificación HMAC igual, no lo repito) ...

    data = request.get_json()
    print("📩 Webhook recibido:", data)

    tipo_evento = data.get("tipo")
    datos = data.get("datos", {})

    # Extraer telegram_id del ref (igual que antes)
    telegram_id = None
    try:
        telegram_id = datos.get("checkout", {}).get("ref") or data.get("ref")
    except:
        telegram_id = None

    if not telegram_id:
        print("❌ No se encontró ref")
        return jsonify({"error": "Usuario no identificado"}), 400

    try:
        telegram_id = int(telegram_id)
    except:
        return jsonify({"error": "ref inválido"}), 400

    plan_comprado = None

    # --- MEMBRESÍAS (Copper, Silver) ---
    if tipo_evento in ["membership.started", "membership.updated"]:
        # Solo procesar si está activa y no es cancelación
        estado = datos.get("estado") or datos.get("status")
        cancelado = datos.get("cancelado") or datos.get("canceled")
        cancel_at_period_end = datos.get("cancel_at_period_end") == "true"

        if estado == "active" and not cancelado and not cancel_at_period_end:
            nivel = (datos.get("nombre_de_nivel_de_membresía") or datos.get("membership_level_name", "")).lower()
            if nivel in ["copper", "silver"]:
                plan_comprado = nivel
            else:
                print(f"Nivel no reconocido: {nivel}")
                return jsonify({"error": "Nivel no reconocido"}), 400
        else:
            # Es una actualización de cancelación, la ignoramos (ya manejada en otros casos)
            return jsonify({"success": True, "message": "Evento de cancelación ignorado"}), 200

    # --- PRODUCTOS DIGITALES (Gold, Platinum, Diamond) ---
    elif tipo_evento == "extra_purchase.created":
        extras = datos.get("extras", [])
        if extras:
            product_id = str(extras[0].get("id"))
            product_to_plan = {
                "510546": "gold",
                "510549": "platinum",
                "510552": "diamond"
            }
            plan_comprado = product_to_plan.get(product_id)

    elif tipo_evento == "membership.cancelled":
        # Manejar cancelación inmediata (opcional)
        print(f"Cancelación para usuario {telegram_id}")
        # Aquí puedes desactivar la membresía si quieres
        return jsonify({"success": True}), 200

    else:
        print(f"Evento ignorado: {tipo_evento}")
        return jsonify({"success": True}), 200

    if not plan_comprado:
        return jsonify({"error": "No se pudo determinar el plan"}), 400

    # Activar membresía
    exito = activar_usuario(telegram_id, plan_comprado, ADMIN_ID)
    if exito:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Error al activar"}), 500

# ============ NUEVOS ENDPOINTS PARA PRODUCCIÓN ============

@app.route("/api/usuario", methods=["POST"])
def api_usuario():
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
        mem_res = supabase_service.table("membresias_activas") \
            .select("*, membresias_planes(*)") \
            .eq("usuario_id", usuario["id"]) \
            .eq("estado", "activa") \
            .gte("fecha_fin", hoy) \
            .execute()
        membresia = mem_res.data[0] if mem_res.data else None

    return jsonify({
        "usuario": usuario,
        "membresia": membresia
    })
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

@app.route("/api/solicitar_cambio_plan", methods=["POST"])
def solicitar_cambio_plan():
    data = request.get_json()
    telegram_id = data.get("telegram_id")
    nuevo_plan_id = data.get("nuevo_plan_id")

    if not telegram_id or not nuevo_plan_id:
        return jsonify({"error": "Faltan datos"}), 400

    # Obtener usuario
    usuario_res = supabase_service.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
    if not usuario_res.data:
        return jsonify({"error": "Usuario no encontrado"}), 404

    usuario = usuario_res.data[0]

    # Obtener membresía activa actual
    hoy = datetime.now().isoformat()
    mem_res = supabase_service.table("membresias_activas") \
        .select("*, membresias_planes(*)") \
        .eq("usuario_id", usuario["id"]) \
        .eq("estado", "activa") \
        .gte("fecha_fin", hoy) \
        .execute()

    if not mem_res.data:
        return jsonify({"error": "No tienes una membresía activa"}), 400

    membresia_actual = mem_res.data[0]
    plan_actual = membresia_actual["membresias_planes"]

    # Verificar que el nuevo plan sea realmente inferior (por ejemplo, menos pedidos o menor precio)

    plan_nuevo_res = supabase_service.table("membresias_planes").select("*").eq("id", nuevo_plan_id).execute()
    if not plan_nuevo_res.data:
        return jsonify({"error": "Plan no válido"}), 400

    plan_nuevo = plan_nuevo_res.data[0]
    if plan_nuevo["pedidos_por_mes"] > plan_actual["pedidos_por_mes"]:
        return jsonify({"error": "El plan seleccionado no es inferior al actual"}), 400

    # Registrar el plan futuro en la membresía activa
    supabase_service.table("membresias_activas") \
        .update({"plan_futuro": nuevo_plan_id}) \
        .eq("id", membresia_actual["id"]) \
        .execute()

    # Notificar al usuario
    try:
        bot.send_message(
            telegram_id,
            f"🔄 Has solicitado cambiar a *{plan_nuevo['nombre'].upper()}* al finalizar tu período actual.\n"
            f"📅 Tu membresía actual vence el {datetime.fromisoformat(membresia_actual['fecha_fin']).strftime('%d/%m/%Y')}.\n"
            f"Después de esa fecha, se activará tu nuevo plan.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error notificando al usuario: {e}")

    return jsonify({"success": True, "mensaje": "Cambio programado correctamente"})

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