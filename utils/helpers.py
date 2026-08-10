"""
Funciones helper y utilidades
"""
from config import ADMIN_IDS, TMDB_API_KEY, TMDB_BASE
import requests


def check_admin(data):
    """
    Verifica si el admin_id en data es válido
    Tolera int y string
    """
    try:
        return int(data.get("admin_id", 0)) in ADMIN_IDS
    except (ValueError, TypeError):
        return False


def tmdb_get(path, params=None):
    """
    Realiza llamada a TMDB API
    
    Args:
        path: Endpoint relativo (ej: "/movie/550")
        params: Parámetros adicionales
    
    Returns:
        JSON response
    """
    params = params or {}
    params["api_key"] = TMDB_API_KEY
    params["language"] = "es-MX"
    
    try:
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise Exception(f"Error en TMDB API: {e}")