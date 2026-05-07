"""
Servicio de contenido
- Importar desde TMDB
- Publicar en canales
- Gestionar catálogo
"""
from datetime import datetime, timezone
from supabase import create_client
import telebot
import requests
from config import (
    SUPABASE_SERVICE_KEY, SUPABASE_URL, BOT_TOKEN,
    TMDB_API_KEY, TMDB_BASE, TMDB_IMG, TIPO_TMDB,
    CANAL_PUBLICO_ID, CANAL_PRIVADO_ID, BOT_USERNAME
)
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)


def tmdb_get(path, params=None):
    """Realiza llamada a TMDB API"""
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    params["language"] = "es-MX"
    try:
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"Error en TMDB API: {e}")
        raise


def importar_desde_tmdb(tmdb_id: int, tipo: str) -> dict:
    """
    Importa contenido desde TMDB
    
    Args:
        tmdb_id: ID de TMDB
        tipo: 'pelicula', 'serie', 'anime'
    
    Returns:
        dict con datos del contenido
    """
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
        "titulo": titulo,
        "tipo": tipo,
        "genero": genero,
        "año": año,
        "imagen_url": imagen_url,
        "sinopsis": sinopsis,
        "rating": rating,
        "tmdb_id": tmdb_id,
        "disponible": True,
        "destacado": False,
    }


def generar_estrellas(rating: float) -> str:
    """Genera estrellas para rating"""
    if not rating:
        return "☆☆☆☆☆"
    estrellas_llenas = round(rating / 2)
    estrellas_vacias = 5 - estrellas_llenas
    return "★" * estrellas_llenas + "☆" * estrellas_vacias


def construir_caption(item: dict) -> str:
    """Construye caption para canal"""
    tipo_emoji = {"pelicula": "🎬", "serie": "📺", "anime": "⛩️"}.get(item.get("tipo"), "🎬")
    tipo_label = {"pelicula": "PELÍCULA", "serie": "SERIE", "anime": "ANIME"}.get(item.get("tipo"), "")
    rating = item.get("rating") or 0
    estrellas = generar_estrellas(float(rating))
    rating_str = f"{rating:.1f}/10" if rating else "N/D"
    generos = item.get("genero") or "Sin género"
    año = item.get("año") or "—"
    titulo = item.get("titulo") or "Sin título"
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
    """Construye botones para canal"""
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
    """Envía a un canal específico"""
    try:
        if imagen:
            bot.send_photo(
                chat_id=canal_id,
                photo=imagen,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=markup
            )
        else:
            bot.send_message(
                chat_id=canal_id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=markup
            )
        logger.info(f"✅ Enviado a {canal_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error enviando a {canal_id}: {e}")
        return False


def enviar_contenido_al_canal(item: dict) -> bool:
    """Envía a ambos canales de difusión"""
    caption = construir_caption(item)
    markup = construir_botones_canal(item)
    imagen = item.get("imagen_url", "")
    ok_publico = _enviar_a_un_canal(CANAL_PUBLICO_ID, caption, markup, imagen)
    ok_privado = _enviar_a_un_canal(CANAL_PRIVADO_ID, caption, markup, imagen)
    return ok_publico or ok_privado


def obtener_siguiente_contenido_a_publicar():
    """
    Obtiene próximo contenido a publicar sin repetir
    Reinicia ciclo cuando se publica todo el catálogo
    """
    logger.info("🔍 Buscando contenido para publicar...")

    # IDs históricos
    todos_publicados = supabase.table("publicaciones_canal").select("contenido_id").execute()
    ids_historicos = list({p["contenido_id"] for p in todos_publicados.data})
    logger.info(f"📊 Publicados históricos: {len(ids_historicos)} ítems")

    # Total disponibles
    total_res = supabase.table("contenido").select("id", count="exact").eq("disponible", True).execute()
    total_disponibles = total_res.count or 0

    # Reiniciar si ya se publicó todo
    if len(ids_historicos) >= total_disponibles and total_disponibles > 0:
        logger.info(f"🔄 Catálogo completo publicado ({total_disponibles} ítems). Reiniciando...")
        supabase.table("publicaciones_canal").delete().neq("id", 0).execute()
        ids_historicos = []

    # Buscar siguiente
    query = supabase.table("contenido").select("*").eq("disponible", True)
    for excluido_id in ids_historicos:
        query = query.neq("id", excluido_id)

    resultado = query.order("año", desc=True).order("id", desc=True).limit(1).execute()
    
    if resultado.data:
        item = resultado.data[0]
        logger.info(f"✅ Siguiente a publicar: {item['titulo']}")
        return item
    
    logger.warning("⚠️ Sin contenido disponible")
    return None


def registrar_publicacion(contenido_id: int):
    """Registra publicación en BD"""
    try:
        supabase.table("publicaciones_canal").insert({
            "contenido_id": contenido_id,
            "publicado_en": datetime.now(timezone.utc).isoformat()
        }).execute()
        logger.info(f"✅ Publicación registrada: contenido_id={contenido_id}")
    except Exception as e:
        logger.error(f"⚠️ Error registrando publicación: {e}")