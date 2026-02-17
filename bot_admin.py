	import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
# ============ CANALES PRIVADOS ============
CANAL_PELICULAS_ID = -1003890553566
CANAL_SERIES_ID = -1003879512007
# ============ GRUPO DE COMANDOS ============
GRUPO_COMANDOS_ID = -1003871199698

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
        plan_result = supabase.table('membresias_planes').select('*').eq('nombre', membresia).execute()
        if not plan_result.data:
            bot.send_message(chat_id_admin, "❌ Membresía no válida")
            return False

        plan_data = plan_result.data[0]
        fecha_vencimiento = datetime.now() + timedelta(days=plan_data['duracion_dias'])

        usuario_result = supabase.table('usuarios').select('*').eq('telegram_id', user_id).execute()

        if not usuario_result.data:
            nombre = f"Usuario_{user_id}"
        else:
            nombre = usuario_result.data[0].get('nombre', f"Usuario_{user_id}")

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

        supabase.table('membresias_activas').update({"estado": "inactiva"}).eq('usuario_id', usuario_id).eq('estado', 'activa').execute()

        supabase.table('membresias_activas').insert({
            "usuario_id": usuario_id,
            "plan_id": plan_data['id'],
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": fecha_vencimiento.isoformat(),
            "estado": "activa",
            "metodo_pago": "auto",
            "monto": plan_data['precio_soles']
        }).execute()

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
                # 👈 SIN parse_mode
            )

            bot.send_message(chat_id_admin, f"✅ Usuario {user_id} activado y enlaces enviados")

        except Exception as e:
            bot.send_message(chat_id_admin, f"⚠️ Membresía activada pero error con enlaces: {e}")
            bot.send_message(user_id, f"🎉 Membresía activada. En breve recibirás los enlaces.")

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


# ============ INICIAR ============
print("Bot iniciado...")
bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)