"""Configure Telegram only after the production health check succeeds. No broadcast."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.configure_bot_menu import menu_configuration, apply_configuration


def configure(bot, origin, secret):
    if len(secret) < 32:
        raise ValueError('Falta el secreto del webhook.')
    config = menu_configuration(origin)
    # Retain pending updates; no getUpdates/polling, no deletion of the webhook.
    if not bot.set_webhook(url=origin.rstrip('/') + '/webhook/telegram', secret_token=secret,
                           max_connections=4, drop_pending_updates=False):
        raise RuntimeError('Telegram no confirmó el webhook.')
    apply_configuration(bot, config)
    result = bot.get_webhook_info()
    if result.url != origin.rstrip('/') + '/webhook/telegram':
        raise RuntimeError('La URL activa no coincide.')
    return {'webhook': result.url, 'pending_updates': result.pending_update_count,
            'commands': [r.command for r in bot.get_my_commands(language_code='es')],
            'menu': bot.get_chat_menu_button().text}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    origin = os.getenv('APP_ORIGIN', 'https://cineapp-bot.onrender.com')
    if args.apply:
        if os.getenv('APP_MODE') != 'production':
            parser.error('Requiere APP_MODE=production y la configuración del servidor.')
        import requests
        from telebot import TeleBot
        health = requests.get(origin + '/health', timeout=30)
        health.raise_for_status()
        if health.json().get('mode') != 'production':
            raise RuntimeError('La nueva versión de producción no está lista.')
        result = configure(TeleBot(os.environ['BOT_TOKEN']), origin, os.environ['TELEGRAM_WEBHOOK_SECRET'])
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({'webhook': origin + '/webhook/telegram', **menu_configuration(origin)}, ensure_ascii=False))
