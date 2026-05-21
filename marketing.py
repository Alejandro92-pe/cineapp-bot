"""
marketing.py — Módulo de Marketing y Email para QuehayApp VIP
Separado de main.py para mantener el código limpio y ordenado.

Endpoints incluidos:
  POST /api/admin/marketing/usuarios_sin_pago
  POST /api/admin/marketing/enviar_mensaje
  POST /api/admin/marketing/enviar_email_manual
  GET  /cron/recordatorio_pagos

Email: SOLO Gmail SMTP (App Password). No se usa ningún otro proveedor.
"""

import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Las variables globales se inyectan desde main.py ──────────────────────────
# Se accede a ellas a través de las funciones init_marketing() y los módulos
# importados. Esto evita importaciones circulares.

_supabase    = None
_bot         = None
_ADMIN_ID    = None
_BOT_USERNAME = None

GMAIL_USER      = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD  = os.getenv("GMAIL_PASSWORD", "")   # App Password de Google
GMAIL_FROM_NAME = "QuehayApp VIP"

marketing_bp = Blueprint("marketing", __name__)


def init_marketing(supabase_client, bot_instance, admin_id: int, bot_username: str):
    """Llamar desde main.py justo después de crear la app Flask."""
    global _supabase, _bot, _ADMIN_ID, _BOT_USERNAME
    _supabase     = supabase_client
    _bot          = bot_instance
    _ADMIN_ID     = admin_id
    _BOT_USERNAME = bot_username


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL — GMAIL SMTP
# ══════════════════════════════════════════════════════════════════════════════

def enviar_email(dest: str, asunto: str, html: str) -> bool:
    """Envía email via Gmail SMTP con App Password de Google."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        print("⚠️ Gmail no configurado (GMAIL_USER / GMAIL_PASSWORD)")
        return False
    if not dest or "@" not in dest:
        print(f"⚠️ Email destino inválido: {dest}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"]    = f"{GMAIL_FROM_NAME} <{GMAIL_USER}>"
        msg["To"]      = dest
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(GMAIL_USER, GMAIL_PASSWORD)
            srv.sendmail(GMAIL_USER, dest, msg.as_string())
        print(f"✅ Email enviado a {dest}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail: error de autenticación — verifica GMAIL_USER y GMAIL_PASSWORD (App Password)")
        return False
    except Exception as e:
        print(f"❌ Email error {dest}: {e}")
        return False


def _html_recordatorio(nombre: str, plan: str, monto, bot_username: str) -> str:
    return (
        "<html><body style='font-family:Arial,sans-serif;background:#0d0d0f;color:#f0f0f2;padding:20px'>"
        "<div style='max-width:460px;margin:0 auto;background:#17171a;border-radius:12px;"
        "padding:24px;border:1px solid rgba(255,255,255,0.08)'>"
        f"<h2 style='color:#e8b04b'>👋 Hola {nombre},</h2>"
        f"<p style='color:#aaa;line-height:1.6'>Empezaste a activar tu membresía "
        f"<b style='color:#fff'>{plan.upper()}</b> (S/{monto}) pero no completaste el pago.</p>"
        "<div style='text-align:center;margin:20px 0'>"
        f"<a href='https://t.me/{bot_username}?start=planes' "
        "style='background:#e8b04b;color:#1a1200;font-weight:700;padding:12px 28px;"
        "border-radius:8px;text-decoration:none;display:inline-block'>✅ Completar membresía</a></div>"
        "<p style='color:#666;font-size:12px;text-align:center'>QuehayApp VIP — "
        "Si no reconoces este mensaje, ignóralo.</p>"
        "</div></body></html>"
    )


def _html_bienvenida(nombre: str, plan: str, bot_username: str) -> str:
    return (
        "<html><body style='font-family:Arial,sans-serif;background:#0d0d0f;color:#f0f0f2;padding:20px'>"
        "<div style='max-width:460px;margin:0 auto;background:#17171a;border-radius:12px;"
        "padding:24px;border:1px solid rgba(255,255,255,0.08)'>"
        f"<h2 style='color:#e8b04b'>🎉 ¡Bienvenido al VIP, {nombre}!</h2>"
        f"<p style='color:#aaa;line-height:1.6'>Tu membresía "
        f"<b style='color:#fff'>{plan.upper()}</b> fue activada con éxito.</p>"
        "<div style='text-align:center;margin:20px 0'>"
        f"<a href='https://t.me/{bot_username}?start=miniapp' "
        "style='background:#e8b04b;color:#1a1200;font-weight:700;padding:12px 28px;"
        "border-radius:8px;text-decoration:none;display:inline-block'>🎬 Ir a la Mini App</a></div>"
        "</div></body></html>"
    )


def _html_mensaje_marketing(nombre: str, mensaje: str, bot_username: str) -> str:
    """Email HTML para envíos manuales de marketing."""
    # Convertir saltos de línea a <br> y *negrita* básico
    html_msg = mensaje.replace("\n", "<br>")
    return (
        "<html><body style='font-family:Arial,sans-serif;background:#0d0d0f;color:#f0f0f2;padding:20px'>"
        "<div style='max-width:460px;margin:0 auto;background:#17171a;border-radius:12px;"
        "padding:24px;border:1px solid rgba(255,255,255,0.08)'>"
        f"<p style='color:#aaa;line-height:1.7'>{html_msg}</p>"
        "<div style='text-align:center;margin:20px 0'>"
        f"<a href='https://t.me/{bot_username}?start=planes' "
        "style='background:#e8b04b;color:#1a1200;font-weight:700;padding:12px 28px;"
        "border-radius:8px;text-decoration:none;display:inline-block;margin:5px'>💎 Ver planes VIP</a>"
        f"<a href='https://t.me/{bot_username}?start=miniapp' "
        "style='background:#333;color:#fff;font-weight:700;padding:12px 28px;"
        "border-radius:8px;text-decoration:none;display:inline-block;margin:5px'>🎬 Ver catálogo</a>"
        "</div>"
        "<p style='color:#555;font-size:11px;text-align:center'>QuehayApp VIP</p>"
        "</div></body></html>"
    )


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES INTERNAS
# ══════════════════════════════════════════════════════════════════════════════

def obtener_usuarios_sin_pago() -> list:
    """
    Usuarios sin membresía activa.
    La columna membresia_activa puede ser FALSE o NULL (ambos significan sin membresía).
    Se excluyen solo los TRUE explícitos.
    """
    # Traer TODOS y filtrar en Python — más confiable que depender
    # del tipo booleano en Supabase (puede venir como NULL, False, "false", etc.)
    res = _supabase.table("usuarios").select(
        "id, telegram_id, nombre, email, membresia_activa, membresia_tipo, fecha_inicio, fecha_vencimiento"
    ).order("id", desc=True).execute()

    todos = res.data or []
    # Excluir solo los que tienen membresia_activa = True explícito
    sin_pago = [u for u in todos if not u.get("membresia_activa")]

    # Enriquecer con último pago (en lote para no hacer N queries)
    if sin_pago:
        ids = [u["telegram_id"] for u in sin_pago if u.get("telegram_id")]
        pagos_res = _supabase.table("pagos_manuales") \
            .select("usuario_id, estado, membresia_comprada, fecha_pago") \
            .in_("usuario_id", ids) \
            .order("fecha_pago", desc=True).execute()

        # Construir dict telegram_id → último pago
        ultimo_pago_map = {}
        for p in (pagos_res.data or []):
            uid = p["usuario_id"]
            if uid not in ultimo_pago_map:
                ultimo_pago_map[uid] = p

        for u in sin_pago:
            u["ultimo_pago"] = ultimo_pago_map.get(u["telegram_id"])

    return sin_pago


def recordatorio_pagos_pendientes():
    """
    Detecta pagos en estado 'pendiente' de más de 24h y envía recordatorio
    UNA SOLA VEZ por pago (anti-spam via columna recordatorio_enviado).

    SQL necesario en Supabase (ejecutar una vez si no existe):
      ALTER TABLE pagos_manuales
        ADD COLUMN IF NOT EXISTS recordatorio_enviado BOOLEAN DEFAULT false,
        ADD COLUMN IF NOT EXISTS recordatorio_enviado_en TIMESTAMPTZ DEFAULT NULL;
    """
    hace_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    pendientes = _supabase.table("pagos_manuales") \
        .select("*, usuarios!inner(*)") \
        .eq("estado", "pendiente") \
        .eq("recordatorio_enviado", False) \
        .lt("fecha_pago", hace_24h) \
        .execute()

    print(f"DEBUG marketing cron: {len(pendientes.data)} pagos sin recordatorio")

    for p in pendientes.data:
        u      = p.get("usuarios", {})
        tid    = u.get("telegram_id")
        nombre = u.get("nombre", "")
        email  = u.get("email", "")
        plan   = p.get("membresia_comprada", "").upper()
        monto  = p.get("monto", "?")

        # ── Telegram ──
        if tid:
            try:
                markup = InlineKeyboardMarkup(row_width=1)
                markup.add(
                    InlineKeyboardButton("✅ Completar mi membresía",
                        url=f"https://t.me/{_BOT_USERNAME}?start=planes"),
                    InlineKeyboardButton("❓ Tengo una duda",
                        url=f"https://t.me/{_BOT_USERNAME}"),
                )
                _bot.send_message(
                    tid,
                    f"👋 Hola *{nombre}*,\n\n"
                    f"Vimos que empezaste a activar tu membresía *{plan}* "
                    f"(S/{monto}) pero no completaste el pago.\n\n"
                    "¿Necesitas ayuda? ¡Estamos aquí! 😊",
                    parse_mode="Markdown", reply_markup=markup
                )
                print(f"✅ Recordatorio Telegram → {tid}")
            except Exception as e:
                print(f"⚠️ Error Telegram {tid}: {e}")

        # ── Gmail ──
        if email:
            try:
                html = _html_recordatorio(nombre, plan.lower(), monto, _BOT_USERNAME)
                enviar_email(email, f"¿Completamos tu membresía {plan}? 🎬", html)
            except Exception as e:
                print(f"⚠️ Error email {email}: {e}")

        # Marcar como enviado aunque haya fallado (evita spam)
        _supabase.table("pagos_manuales").update({
            "recordatorio_enviado":    True,
            "recordatorio_enviado_en": datetime.now(timezone.utc).isoformat()
        }).eq("id", p["id"]).execute()


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS FLASK
# ══════════════════════════════════════════════════════════════════════════════

def _check_admin(data: dict) -> bool:
    try:
        return int(data.get("admin_id", 0)) == _ADMIN_ID
    except (ValueError, TypeError):
        return False


@marketing_bp.route("/api/admin/marketing/usuarios_sin_pago", methods=["POST"])
def api_usuarios_sin_pago():
    data = request.get_json(force=True, silent=True) or {}
    if not _check_admin(data):
        return jsonify({"error": "No autorizado"}), 403
    try:
        usuarios = obtener_usuarios_sin_pago()
        print(f"DEBUG marketing: {len(usuarios)} usuarios sin membresía activa")
        return jsonify({"usuarios": usuarios, "total": len(usuarios)}), 200
    except Exception as e:
        import traceback
        print(f"❌ usuarios_sin_pago ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@marketing_bp.route("/api/admin/marketing/enviar_mensaje", methods=["POST"])
def api_enviar_mensaje_marketing():
    """
    Envío de mensaje de Telegram individual o masivo a usuarios sin membresía.
    Body: { admin_id, telegram_ids: [id,...] | "todos", mensaje, con_botones }
    """
    data = request.get_json(force=True, silent=True) or {}
    if not _check_admin(data):
        return jsonify({"error": "No autorizado"}), 403

    mensaje     = data.get("mensaje", "").strip()
    ids_target  = data.get("telegram_ids", [])
    con_botones = data.get("con_botones", True)

    if not mensaje:
        return jsonify({"error": "mensaje requerido"}), 400

    if ids_target == "todos":
        usuarios   = obtener_usuarios_sin_pago()
        ids_target = [u["telegram_id"] for u in usuarios if u.get("telegram_id")]

    markup = None
    if con_botones:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("💎 Ver planes VIP",
                url=f"https://t.me/{_BOT_USERNAME}?start=planes"),
            InlineKeyboardButton("🎬 Explorar catálogo",
                url=f"https://t.me/{_BOT_USERNAME}?start=miniapp"),
        )

    enviados = errores = 0
    for tid in ids_target:
        try:
            _bot.send_message(int(tid), mensaje, parse_mode="Markdown", reply_markup=markup)
            enviados += 1
            time.sleep(0.05)   # evita flood de Telegram
        except Exception as e:
            print(f"⚠️ Error enviando Telegram a {tid}: {e}")
            errores += 1

    return jsonify({"success": True, "enviados": enviados, "errores": errores}), 200


@marketing_bp.route("/api/admin/marketing/enviar_email_manual", methods=["POST"])
def api_enviar_email_marketing():
    """
    Envío de email manual via Gmail a usuarios sin membresía que tengan email.
    Body: { admin_id, telegram_ids: [id,...] | "todos", asunto, mensaje }

    El email siempre se envía desde Gmail (GMAIL_USER con App Password).
    """
    data = request.get_json(force=True, silent=True) or {}
    if not _check_admin(data):
        return jsonify({"error": "No autorizado"}), 403

    if not GMAIL_USER or not GMAIL_PASSWORD:
        return jsonify({
            "error": "Gmail no configurado. Agrega GMAIL_USER y GMAIL_PASSWORD (App Password) en las variables de entorno de Render."
        }), 500

    ids_target = data.get("telegram_ids", [])
    asunto     = data.get("asunto", "🎬 Oferta especial — QuehayApp VIP").strip()
    mensaje    = data.get("mensaje", "").strip()

    if not mensaje:
        return jsonify({"error": "mensaje requerido"}), 400

    # Obtener usuarios con email
    if ids_target == "todos":
        usuarios = obtener_usuarios_sin_pago()
    else:
        usuarios = []
        for tid in ids_target:
            res = _supabase.table("usuarios").select("*").eq("telegram_id", tid).execute()
            if res.data:
                usuarios.extend(res.data)

    enviados = errores = sin_email = 0
    for u in usuarios:
        email  = u.get("email", "")
        nombre = u.get("nombre", "Hola")
        if not email or "@" not in email:
            sin_email += 1
            continue
        html = _html_mensaje_marketing(nombre, mensaje, _BOT_USERNAME)
        ok   = enviar_email(email, asunto, html)
        if ok:
            enviados += 1
        else:
            errores += 1
        time.sleep(0.1)   # evita rate limit de Gmail

    return jsonify({
        "success": True,
        "enviados":  enviados,
        "errores":   errores,
        "sin_email": sin_email
    }), 200


@marketing_bp.route("/cron/recordatorio_pagos", methods=["GET"])
def cron_recordatorio_pagos():
    """
    Cron diario — configurar en cron-job.org apuntando a:
    GET https://cineapp-bot.onrender.com/cron/recordatorio_pagos

    Envía recordatorio a pagos pendientes de +24h. Anti-spam incluido.
    """
    try:
        recordatorio_pagos_pendientes()
        return jsonify({"success": True, "message": "Recordatorios procesados"}), 200
    except Exception as e:
        import traceback
        print(f"❌ cron recordatorio: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500
