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
    usuario = supabase.table('usuarios').select('*').eq('telegram_id', user_id).execute()
    
    if not usuario.data:
        supabase.table('usuarios').insert({
            "telegram_id": user_id,
            "nombre": user_name,
            "membresia_activa": False
        }).execute()
        print(f"✅ Usuario creado: {user_name} ({user_id})")
    else:
        supabase.table('usuarios').update({
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

        supabase.table('pagos_manuales').insert({
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
    planes = supabase.table('membresias_planes').select('*').execute()
    
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
    
    planes = supabase.table('membresias_planes').select('*').execute()
    texto = "📋 MEMBRESÍAS DISPONIBLES:\n\n"
    
    for p in planes.data:
        texto += f"{p['nombre'].upper()} - S/{p['precio_soles']} - {p['duracion_dias']} días - {p['pedidos_por_mes']} pedidos\n"
    
    bot.send_message(message.chat.id, texto)

# ============ FUNCIÓN DE ACTIVACIÓN REUTILIZABLE ============
def activar_usuario(user_id, membresia, chat_id_admin):
    try:
        # Verificar si el usuario ya tiene una membresía activa
        usuario_actual = supabase.table("usuarios").select("*").eq("telegram_id", user_id).execute()
        ya_activo = False
        if usuario_actual.data and usuario_actual.data[0].get("membresia_activa"):
            ya_activo = True

        plan_result = supabase.table('membresias_planes').select('*').eq('nombre', membresia).execute()
        if not plan_result.data:
            bot.send_message(chat_id_admin, "❌ Membresía no válida")
            return False

        plan_data = plan_result.data[0]
        fecha_vencimiento = datetime.now() + timedelta(days=plan_data['duracion_dias'])

        if not usuario_actual.data:
            nombre = f"Usuario_{user_id}"
        else:
            nombre = usuario_actual.data[0].get('nombre', f"Usuario_{user_id}")

        # Actualizar tabla usuarios
        usuario_data = {
            "telegram_id": user_id,
            "nombre": nombre,
            "membresia_tipo": membresia,
            "membresia_activa": True,
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "pedidos_mes": 0
        }
        supabase.table('usuarios').upsert(usuario_data, on_conflict='telegram_id').execute()

        usuario_id = supabase.table('usuarios').select('id').eq('telegram_id', user_id).execute().data[0]['id']

        # Desactivar membresías activas anteriores
        supabase.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', usuario_id).eq('estado', 'activa').execute()

        # Insertar nueva membresía activa
        supabase.table('membresias_activas').insert({
            "usuario_id": usuario_id,
            "plan_id": plan_data['id'],
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": fecha_vencimiento.isoformat(),
            "estado": "activa",
            "metodo_pago": "auto",
            "monto": plan_data['precio_soles']
        }).execute()

        # --- Lógica de enlaces ---
        if ya_activo:
            # Usuario ya estaba activo: NO enviar nuevos enlaces, pero podríamos revocar los anteriores
            # Revocar enlaces anteriores (opcional)
            try:
                # No hay método directo para revocar enlaces antiguos, pero podemos ignorar
                # Simplemente no enviamos nuevos
                bot.send_message(chat_id_admin, f"✅ Usuario {user_id} actualizado a {membresia} (sin nuevos enlaces, ya estaba en el canal)")
                bot.send_message(user_id, f"🎉 ¡Membresía actualizada a {membresia.upper()}! Sigues teniendo acceso a los canales.")
            except Exception as e:
                print(f"Error notificando actualización: {e}")
        else:
            # Primera activación: enviar enlaces
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
                    f"⚠️ Enlaces de USO ÚNICO - Expiran en 7 días"
                )
                bot.send_message(chat_id_admin, f"✅ Usuario {user_id} activado y enlaces enviados")
            except Exception as e:
                bot.send_message(chat_id_admin, f"⚠️ Membresía activada pero error con enlaces: {e}")
                bot.send_message(user_id, f"🎉 Membresía activada. En breve recibirás los enlaces.")

        # Mensaje de confirmación genérico
        bot.send_message(
            user_id,
            f"🎉 *¡Membresía Activada!*\n\n"
            f"💎 Plan: {membresia.upper()}\n"
            f"📅 Vence: {fecha_vencimiento.strftime('%d/%m/%Y')}",
            parse_mode="Markdown"
        )
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
        usuarios_activos = supabase.table('usuarios') \
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
        
@bot.message_handler(func=lambda message: True)
def procesar_auto_activar(message):

    if message.chat.id != GRUPO_COMANDOS_ID:
        return

    texto = message.text.strip()

    if not texto.startswith("auto_activar"):
        return

    try:
        partes = texto.split()

        if len(partes) < 3:
            return

        user_id = int(partes[1])
        membresia = partes[2].lower()

        print("🔥 EJECUTANDO activar_usuario")

        activar_usuario(user_id, membresia, message.chat.id)

    except Exception as e:
        print("❌ ERROR:", e)

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
        usuario = supabase.table('usuarios').select('*').eq('telegram_id', user_id).execute()
        
        if not usuario.data:
            bot.send_message(message.chat.id, f"❌ Usuario {user_id} no encontrado")
            return
            
        usuario_data = usuario.data[0]
        usuario_id = usuario_data['id']
        
        supabase.table('usuarios').update({"membresia_activa": False}).eq('telegram_id', user_id).execute()
        supabase.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', usuario_id).eq('estado', 'activa').execute()
        
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
        usuario = supabase.table('usuarios').select('*').eq('telegram_id', user_id).execute()
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
            supabase.table('invitaciones').insert([
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
        pago_res = supabase.table("pagos_manuales").select("*").eq("id", pago_id).execute()
        if not pago_res.data:
            return jsonify({"error": "Pago no encontrado"}), 404

        pago = pago_res.data[0]

        # 2️⃣ Obtener usuario
        usuario_res = supabase.table("usuarios").select("*").eq("telegram_id", pago["usuario_id"]).execute()
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
        supabase.table("pagos_manuales").update({
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
    usuarios = supabase.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", ahora) \
        .execute()

    for u in usuarios.data:
        # Desactivar membresía en usuarios
        supabase.table("usuarios").update({
            "membresia_activa": False
        }).eq("id", u["id"]).execute()

        # Opcional: también podrías desactivar el registro en membresias_activas
        supabase.table("membresias_activas").update({
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
    limpiar_membresias_vencidas()  # Limpia vencidas antes de validar

    try:
        data = request.get_json()
        telegram_id = data.get("telegram_id")
        titulo = data.get("titulo")
        tipo = data.get("tipo")

        if not telegram_id or not titulo:
            return jsonify({"error": "Datos incompletos"}), 400

        # 1️⃣ Buscar usuario por telegram_id
        usuario_res = supabase.table("usuarios") \
            .select("*") \
            .eq("telegram_id", telegram_id) \
            .execute()

        if not usuario_res.data:
            return jsonify({"error": "Usuario no encontrado"}), 404

        usuario = usuario_res.data[0]

        # 2️⃣ Verificar membresía activa
        if not usuario.get("membresia_activa"):
            return jsonify({"error": "No tienes membresía activa"}), 403

        # 3️⃣ Obtener la membresía activa actual desde membresias_activas
        hoy = datetime.now().isoformat()
        membresia_activa_res = supabase.table("membresias_activas") \
            .select("*, membresias_planes(*)") \
            .eq("usuario_id", usuario["id"]) \
            .eq("estado", "activa") \
            .gte("fecha_fin", hoy) \
            .order("fecha_fin", desc=True) \
            .limit(1) \
            .execute()

        if not membresia_activa_res.data:
            # Esto no debería pasar si membresia_activa es true, pero por si acaso
            return jsonify({"error": "No se encontró membresía activa válida"}), 403

        membresia_activa = membresia_activa_res.data[0]
        plan = membresia_activa["membresias_planes"]

        # 4️⃣ Validar que el plan permita pedidos
        if plan["pedidos_por_mes"] == 0:
            return jsonify({"error": "Tu plan no incluye pedidos. Mejora tu membresía."}), 403

        # 5️⃣ Contar pedidos en el período de esta membresía activa
        pedidos_res = supabase.table("pedidos") \
            .select("*") \
            .eq("usuario_id", telegram_id) \
            .gte("fecha_pedido", membresia_activa["fecha_inicio"]) \
            .lte("fecha_pedido", membresia_activa["fecha_fin"]) \
            .execute()

        pedidos_actuales = len(pedidos_res.data)
        limite = plan["pedidos_por_mes"]

        if pedidos_actuales >= limite:
            return jsonify({"error": "Has alcanzado el límite de tu plan"}), 403

        # 6️⃣ Insertar pedido
        supabase.table("pedidos").insert({
            "usuario_id": telegram_id,
            "titulo_pedido": titulo,
            "tipo": tipo,
            "estado": "pendiente",
            "fecha_pedido": datetime.now().isoformat()
        }).execute()

        restantes = limite - (pedidos_actuales + 1)

        # 🔔 Notificar ADMIN
        bot.send_message(
            ADMIN_ID,
            f"📥 NUEVO PEDIDO\n\n"
            f"👤 Usuario: {telegram_id}\n"
            f"🎬 Título: {titulo}\n"
            f"📦 Plan: {plan['nombre']}\n"
            f"📊 Restantes: {restantes}"
        )

        # 🔔 Confirmar usuario
        bot.send_message(
            telegram_id,
            f"✅ Pedido enviado correctamente.\n\n"
            f"📦 Te quedan {restantes} pedidos disponibles."
        )

        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ ERROR crear_pedido:", str(e))
        # Devuelve el error específico para depuración (en producción puedes ocultarlo)
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
        pedidos_res = supabase.table("pedidos") \
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
        pedido_res = supabase.table("pedidos") \
            .select("*, usuarios!inner(*)") \
            .eq("id", pedido_id) \
            .execute()

        if not pedido_res.data:
            response = jsonify({"error": "Pedido no encontrado"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404

        pedido = pedido_res.data[0]

        # Actualizar estado del pedido
        supabase.table("pedidos").update({
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
        pedidos_res = supabase.table("pedidos") \
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
        usuario_res = supabase.table("usuarios") \
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
    usuarios_proximos = supabase.table("usuarios") \
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
    usuarios_muy_proximos = supabase.table("usuarios") \
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
    usuarios_vencidos = supabase.table("usuarios") \
        .select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", hoy) \
        .execute()

    for u in usuarios_vencidos.data:
        # Desactivar en BD
        supabase.table("usuarios").update({"membresia_activa": False}).eq("id", u["id"]).execute()
        supabase.table("membresias_activas").update({"estado": "inactiva"}).eq("usuario_id", u["id"]).eq("estado", "activa").execute()

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
    # Verificar firma HMAC-SHA256
    secret = os.getenv("BUY_ME_A_COFFEE_WEBHOOK_SECRET")
    if not secret:
        print("❌ BUY_ME_A_COFFEE_WEBHOOK_SECRET no está configurado")
        return jsonify({"error": "Configuración incorrecta"}), 500

    signature_header = request.headers.get("x-signature-sha256")
    if not signature_header:
        return jsonify({"error": "Firma no proporcionada"}), 400

    payload = request.get_data()
    expected_signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected_signature}", signature_header):
        return jsonify({"error": "Firma inválida"}), 403

    # Procesar payload
    data = request.get_json()
    print("📩 Webhook recibido:", data)

    # Identificar plan comprado
    plan_comprado = None
    if data.get("type") == "membership.created":
        nivel = data.get("data", {}).get("membership", {}).get("membership_level_name", "").lower()
        if nivel in ["copper", "silver"]:
            plan_comprado = nivel
    elif data.get("type") == "extra_purchase.created":
        product_id = data.get("data", {}).get("extra", {}).get("extra_id")
        # Mapea los IDs reales de tus productos
        product_to_plan = {
            "510546": "gold",        # Reemplaza con el ID real de tu producto Gold
            "510549": "platinum",      # ID de tu producto Platinum
            "510552": "diamond"    # Reemplaza con el ID real de tu producto Diamond
        }
        plan_comprado = product_to_plan.get(str(product_id))

    if not plan_comprado:
        return jsonify({"error": "Plan no identificado"}), 400

    # Extraer telegram_id del parámetro "ref"
    telegram_id = None
    if data.get("data") and data["data"].get("checkout"):
        telegram_id = data["data"]["checkout"].get("ref")
    elif data.get("ref"):
        telegram_id = data.get("ref")

    if not telegram_id:
        print("❌ No se encontró el parámetro 'ref' en el webhook")
        return jsonify({"error": "Usuario no identificado (falta ref)"}), 400

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return jsonify({"error": "ref no es un número válido"}), 400

    # Activar membresía
    exito = activar_usuario(telegram_id, plan_comprado, ADMIN_ID)

    if exito:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Error al activar membresía"}), 500

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