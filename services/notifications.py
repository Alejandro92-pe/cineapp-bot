"""
Servicio de notificaciones inteligente
- Evita duplicados con flags booleanos
- Resetea flags cuando usuario renueva
- Logging detallado
"""
from datetime import datetime, timedelta, timezone
from supabase import create_client
import telebot
from config import (
    SUPABASE_SERVICE_KEY, SUPABASE_URL, BOT_TOKEN, LIMA_TZ,
    CANAL_PELICULAS_ID, CANAL_SERIES_ID, GRUPO_CONTENIDO_ID, ADMIN_ID
)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)


def obtener_usuarios_vencimiento_proximo(dias=3, horas=3):
    """
    Obtiene usuarios próximos a vencer PERO sin notificación enviada.
    
    Retorna: (usuarios_3_dias, usuarios_3_horas)
    """
    ahora = datetime.now(LIMA_TZ)
    hoy = ahora.isoformat()
    
    # 1. USUARIOS CON VENCIMIENTO EN 3 DÍAS (sin notificación previa)
    en_3_dias = (ahora + timedelta(days=dias)).isoformat()
    usuarios_3dias = supabase.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .eq("notificacion_3dias_enviada", False) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3_dias) \
        .execute()
    
    # 2. USUARIOS CON VENCIMIENTO EN 3 HORAS (sin notificación previa)
    en_3h = (ahora + timedelta(hours=horas)).isoformat()
    usuarios_3horas = supabase.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .eq("notificacion_3horas_enviada", False) \
        .gte("fecha_vencimiento", hoy) \
        .lte("fecha_vencimiento", en_3h) \
        .execute()
    
    return usuarios_3dias.data, usuarios_3horas.data


def marcar_notificacion_enviada(usuario_id, tipo_notificacion):
    """
    Marca que una notificación fue enviada (exitosamente)
    
    tipo_notificacion: '3dias', '3horas', 'vencida'
    """
    update_data = {}
    
    if tipo_notificacion == "3dias":
        update_data["notificacion_3dias_enviada"] = True
    elif tipo_notificacion == "3horas":
        update_data["notificacion_3horas_enviada"] = True
    elif tipo_notificacion == "vencida":
        update_data["notificacion_vencida_enviada"] = True
    
    if update_data:
        supabase.table("usuarios").update(update_data).eq("id", usuario_id).execute()
        print(f"✅ Notificación {tipo_notificacion} marcada para usuario {usuario_id}")


def resetear_flags_notificaciones(usuario_id):
    """
    Reseta TODOS los flags cuando el usuario renueva.
    Así puede volver a recibir notificaciones en el próximo período.
    """
    supabase.table("usuarios").update({
        "notificacion_3dias_enviada": False,
        "notificacion_3horas_enviada": False,
        "notificacion_vencida_enviada": False
    }).eq("id", usuario_id).execute()
    
    print(f"🔄 Flags de notificación reseteados para usuario {usuario_id}")


def enviar_notificacion_3dias(usuario):
    """
    Envía notificación de vencimiento en 3 días.
    Retorna True si se envió exitosamente.
    """
    try:
        vence = datetime.fromisoformat(usuario["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
        mensaje = (
            f"⏳ *Tu membresía vence en 3 días* ({vence}).\n\n"
            f"Renueva ahora para no perder el acceso a todo el contenido."
        )
        bot.send_message(usuario["telegram_id"], mensaje, parse_mode="Markdown")
        print(f"✅ Notificación 3 días enviada a {usuario['telegram_id']}")
        return True
    except Exception as e:
        print(f"❌ Error enviando notificación 3 días a {usuario['id']}: {e}")
        return False


def enviar_notificacion_3horas(usuario):
    """
    Envía notificación de vencimiento en 3 horas.
    Retorna True si se envió exitosamente.
    """
    try:
        vence = datetime.fromisoformat(usuario["fecha_vencimiento"]).strftime("%d/%m/%Y %H:%M")
        mensaje = (
            f"⚠️ *¡Tu membresía vence en 3 horas!* ({vence})\n\n"
            f"Este es tu último aviso. Renueva ya para mantener el acceso."
        )
        bot.send_message(usuario["telegram_id"], mensaje, parse_mode="Markdown")
        print(f"✅ Notificación 3 horas enviada a {usuario['telegram_id']}")
        return True
    except Exception as e:
        print(f"❌ Error enviando notificación 3 horas a {usuario['id']}: {e}")
        return False


def desactivar_membresia_vencida(usuario):
    """
    Maneja la desactivación de una membresía que ya venció.
    - Actualiza estado en BD
    - Banea de canales
    - Notifica al usuario
    """
    try:
        # Actualizar estado en BD
        supabase.table("usuarios").update({
            "membresia_activa": False,
            "notificacion_vencida_enviada": True
        }).eq("id", usuario["id"]).execute()
        
        supabase.table("membresias_activas").update({
            "estado": "inactiva"
        }).eq("usuario_id", usuario["id"]).eq("estado", "activa").execute()
        
        # Banear de canales
        canales = [CANAL_PELICULAS_ID, CANAL_SERIES_ID, GRUPO_CONTENIDO_ID]
        for canal in canales:
            try:
                bot.ban_chat_member(chat_id=canal, user_id=usuario["telegram_id"])
                print(f"🚫 Usuario {usuario['telegram_id']} baneado de {canal}")
            except Exception as e:
                print(f"⚠️ Error baneando de {canal}: {e}")
        
        # Notificar
        try:
            bot.send_message(
                usuario["telegram_id"],
                "❌ *Tu membresía ha vencido.* Renueva para seguir disfrutando.",
                parse_mode="Markdown"
            )
            print(f"✅ Notificación de vencimiento enviada a {usuario['telegram_id']}")
        except Exception as e:
            print(f"⚠️ Error notificando vencimiento: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Error desactivando membresía de {usuario['id']}: {e}")
        return False


def verificar_vencimientos():
    """
    CRON principal: verifica y envía notificaciones sin spam.
    
    Lógica:
    1. Busca usuarios con vencimiento en 3 días (sin notificación previa)
    2. Busca usuarios con vencimiento en 3 horas (sin notificación previa)
    3. Busca usuarios cuya membresía ya venció
    4. Para cada grupo, envía notificación SOLO UNA VEZ
    5. Marca los flags para que no se repita
    """
    ahora = datetime.now(LIMA_TZ)
    hoy = ahora.isoformat()
    
    print(f"\n{'='*60}")
    print(f"🕐 CRON VERIFICACIÓN DE VENCIMIENTOS")
    print(f"   Hora Lima: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # === 1. NOTIFICACIÓN EN 3 DÍAS ===
    usuarios_3dias, usuarios_3horas = obtener_usuarios_vencimiento_proximo()
    
    print(f"\n📋 Usuarios próximos en 3 días: {len(usuarios_3dias)}")
    for usuario in usuarios_3dias:
        if enviar_notificacion_3dias(usuario):
            marcar_notificacion_enviada(usuario["id"], "3dias")
    
    # === 2. NOTIFICACIÓN EN 3 HORAS ===
    print(f"\n📋 Usuarios próximos en 3 horas: {len(usuarios_3horas)}")
    for usuario in usuarios_3horas:
        if enviar_notificacion_3horas(usuario):
            marcar_notificacion_enviada(usuario["id"], "3horas")
    
    # === 3. USUARIOS VENCIDOS ===
    usuarios_vencidos = supabase.table("usuarios").select("*") \
        .eq("membresia_activa", True) \
        .lt("fecha_vencimiento", hoy) \
        .execute()
    
    print(f"\n📋 Usuarios vencidos: {len(usuarios_vencidos.data)}")
    for usuario in usuarios_vencidos.data:
        desactivar_membresia_vencida(usuario)
    
    print(f"\n{'='*60}")
    print(f"✅ CRON completado")
    print(f"{'='*60}\n")