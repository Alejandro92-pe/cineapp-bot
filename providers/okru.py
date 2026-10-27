"""Canonical OK.ru embeds only; never extract media or accept arbitrary iframes."""
import re
from urllib.parse import urlsplit


def embed_url(value):
    if not isinstance(value,str) or len(value)>2048:return None
    try:
        url=urlsplit(value)
        if url.scheme!='https' or url.netloc not in ('ok.ru','www.ok.ru'):return None
        match=re.fullmatch(r'/video(?:embed)?/([1-9][0-9]{0,19})/?',url.path)
        return f'https://ok.ru/videoembed/{match[1]}?nochat=1' if match else None
    except ValueError:return None
