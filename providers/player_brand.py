"""Documented Vimeus embed customization; no account-wide provider settings."""
from urllib.parse import urlsplit


def quehay_player_params(origin=''):
    # Vimeus /player generates title and theme. Its SDK documents primary_color.
    # The blue theme supplies dark surfaces; a lighter blue keeps controls legible.
    params = {'title': 'QueHay', 'theme': 'blue', 'primary_color': '78b7fb'}
    url = urlsplit(origin)
    if url.scheme == 'https' and url.hostname and not (url.username or url.password or url.query or url.fragment or url.path.strip('/')):
        params['logo_url'] = origin.rstrip('/') + '/static/logo-que-hay-live.png'
    return params
