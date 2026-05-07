"""
Servicio de activación de membresías
- Maneja activación inicial y renovación
- Resetea flags anti-spam cuando renueva
- Hereda días y pedidos restantes al mejorar plan
"""
from datetime import datetime, timedelta
import time
from supabase import create_client
import telebot
from config import (
    SUPABASE_SERVICE_KEY, SUPABASE_URL, BOT_TOKEN,
    CANAL_PELICULAS_ID, CANAL_SERIES_ID, GRUPO_CONTENIDO_ID, ADMIN_ID
)
from services.notifications import resetear_flags_notificaciones

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)


def activar_usuario(user_id, membresia_nombre, chat_id_admin):
    """
    Activa o renueva membresía de un usuario.
    
    Si el usuario YA tiene membresía activa:
    - Hereda días restantes
    - Suma pedidos no usados
    - Reseta flags para nuevas notificaciones
    
    Si es primera vez:
    - Crea membresía nueva
    - Envía enlaces de canales
    
    Retorna: True si se activó correctamente, False si hubo error
    """
    try:
        print(f"\n📝 Activando membresía '{membresia_nombre}' para usuario {user_id}")
        
        # 1. Obtener datos del plan
        plan_result = supabase.table('membresias_planes').select('*') \
            .eq('nombre', membresia_nombre).execute()
        
        if not plan_result.data:
            bot.send_message(chat_id_admin, f"❌ Membresía '{membresia_nombre}' no válida")
            return False
        
        plan_data = plan_result.data[0]
        duracion_plan = plan_data['duracion_dias']
        limite_pedidos_nuevo = plan_data['pedidos_por_mes']
        
        # 2. Verificar si usuario tiene membresía activa
        usuario_actual = supabase.table('usuarios').select('*') \
            .eq('telegram_id', user_id).execute()
        
        tiene_activa = usuario_actual.data and usuario_actual.data[0].get('membresia_activa')
        es_mejora = False
        dias_extra = 0
        pedidos_extra = 0
        plan_anterior_nombre = None
        
        if tiene_activa:
            usuario = usuario_actual.data[0]
            fecha_venc = datetime.fromisoformat(usuario['fecha_vencimiento'])
            dias_rest = (fecha_venc - datetime.now()).days
            
            if dias_rest > 0:
                es_mejora = True
                dias_extra = dias_rest
                plan_anterior_nombre = usuario.get('membresia_tipo', 'anterior')
                
                # Calcular pedidos no usados
                mem_ant = supabase.table('membresias_activas') \
                    .select('fecha_inicio, plan_id') \
                    .eq('usuario_id', usuario['id']) \
                    .eq('estado', 'activa').execute()
                
                if mem_ant.data:
                    fecha_ini_ant = datetime.fromisoformat(mem_ant.data[0]['fecha_inicio'])
                    pedidos_usados = supabase.table('pedidos').select('*', count='exact') \
                        .eq('usuario_id', user_id) \
                        .gte('fecha_pedido', fecha_ini_ant.isoformat()) \
                        .lte('fecha_pedido', datetime.now().isoformat()).execute()
                    
                    usados = pedidos_usados.count if hasattr(pedidos_usados, 'count') else len(pedidos_usados.data)
                    
                    plan_ant = supabase.table('membresias_planes').select('pedidos_por_mes') \
                        .eq('id', mem_ant.data[0]['plan_id']).execute()
                    
                    limite_ant = plan_ant.data[0]['pedidos_por_mes'] if plan_ant.data else 0
                    pedidos_extra = max(0, limite_ant - usados)
                    
                    print(f"   📊 Herencia: {dias_extra} días + {pedidos_extra} pedidos")
        
        # 3. Calcular fecha de vencimiento
        fecha_vencimiento = datetime.now() + timedelta(days=duracion_plan + dias_extra)
        nombre = usuario_actual.data[0].get('nombre', f"Usuario_{user_id}") if usuario_actual.data else f"Usuario_{user_id}"
        
        # 4. Actualizar/crear usuario
        supabase.table('usuarios').upsert({
            "telegram_id": user_id,
            "nombre": nombre,
            "membresia_tipo": membresia_nombre,
            "membresia_activa": True,
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "pedidos_mes": 0
        }, on_conflict='telegram_id').execute()
        
        # 5. Obtener ID interno del usuario
        usuario_id_interno = supabase.table('usuarios').select('id') \
            .eq('telegram_id', user_id).execute().data[0]['id']
        
        # 6. Desactivar membresías previas activas
        supabase.table('membresias_activas').update({"estado": "inactiva"}) \
            .eq('usuario_id', usuario_id_interno).eq('estado', 'activa').execute()
        
        # 7. Crear nueva membresía activa
        supabase.table('membresias_activas').insert({
            "usuario_id": usuario_id_interno,
            "plan_id": plan_data['id'],
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": fecha_vencimiento.isoformat(),
            "estado": "activa",
            "metodo_pago": "auto",
            "monto": plan_data['precio_soles'],
            "pedidos_extra": pedidos_extra
        }).execute()
        
        # 8. RESETEAR FLAGS DE NOTIFICACIONES (¡IMPORTANTE!)
        resetear_flags_notificaciones(usuario_id_interno)
        
        # 9. Si es primera activación, enviar enlaces
        if not tiene_activa:
            print(f"   🎁 Primera activación - enviando enlaces de canales")
            try:
                inv_pelis = bot.create_chat_invite_link(
                    CANAL_PELICULAS_ID, 
                    name=f"U{user_id}_pelis",
                    member_limit=1, 
                    expire_date=int(time.time()) + 604800
                )
                inv_series = bot.create_chat_invite_link(
                    CANAL_SERIES_ID,
                    name=f"U{user_id}_series",
                    member_limit=1,
                    expire_date=int(time.time()) + 604800
                )
                inv_grupo = bot.create_chat_invite_link(
                    GRUPO_CONTENIDO_ID,
                    name=f"U{user_id}_grupo",
                    member_limit=1,
                    expire_date=int(time.time()) + 604800
                )
                
                from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup(row_width=1)
                markup.add(
                    InlineKeyboardButton("🎬 Canal de Películas", url=inv_pelis.invite_link),
                    InlineKeyboardButton("📺 Canal de Series", url=inv_series.invite_link),
                    InlineKeyboardButton("👥 Grupo Privado", url=inv_grupo.invite_link),
                )
                
                bot.send_message(user_id,
                    "🔐 <b>ACCESO A TUS CANALES</b>\n\n"
                    "👇 Toca los botones para unirte\n\n"
                    "⚠️ Enlaces de uso único - expiran en 7 días",
                    parse_mode="HTML", reply_markup=markup)
                
                bot.send_message(user_id,
                    "📍 Únete a los 3 canales, silencialos y usa la MiniApp para ver el contenido")
                
                bot.send_message(chat_id_admin, f"✅ Usuario {user_id} activado y 3 enlaces enviados")
            except Exception as e:
                bot.send_message(chat_id_admin, f"⚠️ Membresía activada pero error con enlaces: {e}")
        else:
            bot.send_message(chat_id_admin, f"✅ Usuario {user_id} renovó {membresia_nombre}")
        
        # 10. Mensaje al usuario
        total_pedidos = limite_pedidos_nuevo + pedidos_extra
        
        if es_mejora:
            mensaje = (
                f"🔄 *¡Mejoraste a {membresia_nombre.upper()}!*\n\n"
                f"Hemos sumado los {dias_extra} días restantes de tu plan {plan_anterior_nombre.capitalize()} "
                f"y tus {pedidos_extra} pedidos no usados.\n"
                f"📅 *Nueva fecha de vencimiento:* {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"🎟 *Pedidos disponibles:* {total_pedidos}\n\n"
                "¡Gracias por confiar en nosotros!"
            )
        else:
            mensaje = (
                f"🎉 *¡Membresía Activada!*\n\n"
                f"💎 Plan: {membresia_nombre.upper()}\n"
                f"📅 Vence: {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"🎟 Pedidos por mes: {limite_pedidos_nuevo}"
            )
        
        bot.send_message(user_id, mensaje, parse_mode="Markdown")
        print(f"   ✅ Usuario {user_id} activado exitosamente")
        return True
    
    except Exception as e:
        print(f"   ❌ Error activando usuario: {e}")
        bot.send_message(chat_id_admin, f"❌ Error en activación: {str(e)}")
        return False