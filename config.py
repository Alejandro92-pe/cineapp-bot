"""
Configuración centralizada de la aplicación
Todos los parámetros en un solo lugar para fácil mantenimiento
"""
import os
from datetime import timezone, timedelta

# ============ VARIABLES DE ENTORNO ============
# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
BOT_USERNAME = os.getenv("BOT_USERNAME", "Popcornqh_admin_bot")

# APIs Externas
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
VIMEUS_VIEW_KEY = os.getenv("VIMEUS_VIEW_KEY", "")

# Render
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", 10000))

# ============ ZONA HORARIA ============
# Zona horaria de Lima (UTC-5)
LIMA_TZ = timezone(timedelta(hours=-5))

# ============ IDs DE CANALES TELEGRAM ============
# Grupo de soporte
GRUPO_SOPORTE_ID = -1003805629374

# Canales VIP (membresías)
CANAL_PELICULAS_ID = -1003890553566
CANAL_SERIES_ID = -1003879512007
GRUPO_CONTENIDO_ID = -1002991571573

# Canales de difusión pública
CANAL_PUBLICO_ID = "@mejoresanimesenlatino"
CANAL_PRIVADO_ID = -1002503337168

# Lista de todos los canales de acceso VIP
CANALES_VIP = [
    CANAL_PELICULAS_ID,
    CANAL_SERIES_ID,
    GRUPO_CONTENIDO_ID,
]

# ============ URLs ============
# Mini App
MINIAPP_URL = "https://cineapp-bot.onrender.com"

# Buy Me A Coffee
BMC_URL = "https://buymeacoffee.com/quehay/extras"
BMC_LINKS = {
    "copper": "https://buymeacoffee.com/quehay/e/517243",
    "silver": "https://buymeacoffee.com/quehay/e/517244",
    "gold": "https://buymeacoffee.com/quehay/e/510546",
    "platinum": "https://buymeacoffee.com/quehay/e/510549",
    "diamond": "https://buymeacoffee.com/quehay/e/510552",
}

# ============ TMDB CONFIG (The Movie Database) ============
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

# Mapeo de tipos de contenido a endpoints de TMDB
TIPO_TMDB = {
    "pelicula": "movie",
    "serie": "tv",
    "anime": "tv",
}

# ============ PARÁMETROS DEL SISTEMA ============
# Tiempo de expiración de enlaces de acceso (en segundos)
INVITE_LINK_EXPIRE_DAYS = 7
INVITE_LINK_EXPIRE_SECONDS = INVITE_LINK_EXPIRE_DAYS * 24 * 60 * 60

# Límite de miembros por enlace
INVITE_LINK_MEMBER_LIMIT = 1

# Timeouts
REQUEST_TIMEOUT = 10  # segundos
TELEGRAM_TIMEOUT = 30  # segundos

# ============ VALIDACIÓN ============
def validate_config():
    """Valida que todos los parámetros requeridos estén configurados"""
    required = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_SERVICE_KEY",
        "BOT_TOKEN",
        "ADMIN_ID",
        "TMDB_API_KEY",
    ]
    
    missing = []
    for param in required:
        if not globals().get(param):
            missing.append(param)
    
    if missing:
        raise ValueError(f"Parámetros faltantes: {', '.join(missing)}")
    
    return True

# Validar al importar
try:
    validate_config()
except ValueError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Config validation: {e}")