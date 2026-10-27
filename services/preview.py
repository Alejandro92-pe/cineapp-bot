"""Explicit HTTPS tunnel mode, still using isolated local storage and disabled bots."""
from urllib.parse import urlsplit


def validate_preview_origin(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or
        not parsed.hostname.endswith(('.ngrok-free.dev', '.ngrok-free.app', '.ngrok.app')) or
        parsed.port is not None or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Usa el origen HTTPS exacto que devuelve ngrok, sin ruta.')
    return origin
