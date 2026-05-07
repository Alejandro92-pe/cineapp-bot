"""
Endpoints Flask para cron y renovación de membresías
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from supabase import create_client
from services.notifications import verificar_vencimientos
from services.membership import activar_usuario
from config import SUPABASE_SERVICE_KEY, SUPABASE_URL, ADMIN_ID

# Blueprint para rutas de cron
cron_bp = Blueprint('cron', __name__)

# Blueprint para rutas de membresías
membership_bp = Blueprint('membership', __name__)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ============================================================
# CRON: VERIFICACIÓN DE VENCIMIENTOS (sin spam)
# ============================================================

@cron_bp.route("/cron/verificar_vencimientos", methods=["GET"])
def cron_verificar_vencimientos():
    """
    Endpoint que ejecuta el cron cada 10 minutos.
    
    MEJORADO:
    - Usa flags booleanos para evitar duplicados
    - Verifica 3 puntos: 3 días, 3 horas, vencidos
    - Solo envía mensajes si el flag está en False
    - Marca flag = True después de enviar
    - Cuando usuario renueva, resetea todos los flags
    
    Ejemplo de llamada:
    curl https://tu-app.com/cron/verificar_vencimientos
    """
    try:
        print("\n🔔 CRON de vencimientos iniciado")
        verificar_vencimientos()
        return jsonify({"status": "OK", "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        print(f"❌ Error en cron: {e}")
        return jsonify({"status": "Error", "error": str(e)}), 500


# ============================================================
# RENOVACIÓN: Cuando usuario compra de nuevo
# ============================================================

@membership_bp.route("/renovar_membresia", methods=["POST"])
def renovar_membresia():
    """
    Endpoint para renovar membresía (admin llama esto después de pago aprobado).
    
    Body esperado:
    {
        "usuario_id": 123456,
        "plan": "gold",
        "admin_id": ADMIN_ID
    }
    
    Lo que hace:
    1. Valida que sea admin
    2. Obtiene datos del plan
    3. Calcula nueva fecha de vencimiento
    4. Resetea flags anti-spam (¡CLAVE!)
    5. Actualiza fecha_ultima_renovacion
    6. Envía confirmación al usuario
    """
    try:
        data = request.get_json()
        
        # Validar admin
        if int(data.get("admin_id", 0)) != ADMIN_ID:
            return jsonify({"error": "No autorizado"}), 403
        
        usuario_id = data.get("usuario_id")
        plan = data.get("plan", "").lower()
        
        if not usuario_id or not plan:
            return jsonify({"error": "usuario_id y plan requeridos"}), 400
        
        # Activar usuario (que es lo mismo que renovar)
        ok = activar_usuario(usuario_id, plan, ADMIN_ID)
        
        if not ok:
            return jsonify({"error": "Error activando membresía"}), 500
        
        # Registrar fecha de última renovación
        usuario = supabase.table('usuarios').select('id') \
            .eq('telegram_id', usuario_id).execute()
        
        if usuario.data:
            supabase.table('usuarios').update({
                "fecha_ultima_renovacion": datetime.now().isoformat()
            }).eq('id', usuario.data[0]['id']).execute()
        
        return jsonify({"success": True, "message": "Membresía renovada exitosamente"}), 200
    
    except Exception as e:
        print(f"❌ Error en renovación: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# DIAGNÓSTICO: Ver estado de flags de un usuario
# ============================================================

@membership_bp.route("/admin/estado_notificaciones", methods=["POST"])
def ver_estado_notificaciones():
    """
    Endpoint para diagnosticar el estado de flags de un usuario.
    
    Útil para debugging. Solo admin.
    
    Body:
    {
        "admin_id": ADMIN_ID,
        "usuario_id": 123456
    }
    """
    try:
        data = request.get_json()
        
        if int(data.get("admin_id", 0)) != ADMIN_ID:
            return jsonify({"error": "No autorizado"}), 403
        
        usuario_id = data.get("usuario_id")
        
        usuario = supabase.table('usuarios').select(
            'id,telegram_id,membresia_tipo,membresia_activa,fecha_vencimiento,'
            'notificacion_3dias_enviada,notificacion_3horas_enviada,notificacion_vencida_enviada'
        ).eq('telegram_id', usuario_id).execute()
        
        if not usuario.data:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        u = usuario.data[0]
        return jsonify({
            "usuario_id": u['telegram_id'],
            "plan": u['membresia_tipo'],
            "activa": u['membresia_activa'],
            "vencimiento": u['fecha_vencimiento'],
            "flags": {
                "notificacion_3dias_enviada": u['notificacion_3dias_enviada'],
                "notificacion_3horas_enviada": u['notificacion_3horas_enviada'],
                "notificacion_vencida_enviada": u['notificacion_vencida_enviada']
            }
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# RESET MANUAL: Limpiar flags (para testing)
# ============================================================

@membership_bp.route("/admin/resetear_flags", methods=["POST"])
def resetear_flags_manual():
    """
    Endpoint para resetear FLAGS de un usuario (testing/debugging).
    
    Body:
    {
        "admin_id": ADMIN_ID,
        "usuario_id": 123456
    }
    """
    try:
        data = request.get_json()
        
        if int(data.get("admin_id", 0)) != ADMIN_ID:
            return jsonify({"error": "No autorizado"}), 403
        
        usuario_id = data.get("usuario_id")
        
        usuario = supabase.table('usuarios').select('id') \
            .eq('telegram_id', usuario_id).execute()
        
        if not usuario.data:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        uid_interno = usuario.data[0]['id']
        
        supabase.table('usuarios').update({
            "notificacion_3dias_enviada": False,
            "notificacion_3horas_enviada": False,
            "notificacion_vencida_enviada": False
        }).eq('id', uid_interno).execute()
        
        return jsonify({"success": True, "message": "Flags reseteados"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500