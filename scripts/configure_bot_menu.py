"""Prepare the Telegram menu. No writes unless explicitly run with --apply at deployment."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from telegram_bot.assistant import COMMANDS
from security import OWNER_ID


def menu_configuration(origin):
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('APP_ORIGIN debe ser el origen HTTPS público de QueHay.')
    commands = [{'command': name, 'description': description} for name, description in COMMANDS]
    return {'commands': commands, 'owner_commands': commands + [
        {'command': 'publicar', 'description': 'Anunciar un título: /publicar ID'}],
        'menu_button': {'type': 'web_app', 'text': 'Abrir QueHay', 'web_app': {'url': origin.rstrip('/')}}}


def apply_configuration(bot, config):
    from telebot.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat, MenuButtonWebApp, WebAppInfo
    # Replace both default and Spanish command sets, including a prior owner-specific menu.
    for language in ('', 'es'):
        for scope in (None, BotCommandScopeAllPrivateChats()):
            bot.set_my_commands([BotCommand(**row) for row in config['commands']], scope=scope, language_code=language)
        bot.set_my_commands([BotCommand(**row) for row in config['owner_commands']],
                            scope=BotCommandScopeChat(OWNER_ID), language_code=language)
    menu = MenuButtonWebApp(type='web_app', text='Abrir QueHay', web_app=WebAppInfo(**config['menu_button']['web_app']))
    bot.set_chat_menu_button(menu_button=menu)
    bot.set_chat_menu_button(chat_id=OWNER_ID, menu_button=menu)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = menu_configuration(os.getenv('APP_ORIGIN', 'https://cineapp-bot.onrender.com'))
    if args.apply:
        if os.getenv('APP_MODE') == 'local' or not os.getenv('BOT_TOKEN'):
            parser.error('La aplicación del menú requiere el entorno de producción y BOT_TOKEN.')
        from telebot import TeleBot
        apply_configuration(TeleBot(os.environ['BOT_TOKEN']), config)
        print('Menú de Telegram actualizado.')
    else:
        print(json.dumps(config, ensure_ascii=False, indent=2))
