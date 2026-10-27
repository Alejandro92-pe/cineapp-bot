"""Render actual bot responses using an offline transport and disposable database."""
import hashlib
from html import escape
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_support import LocalBot, LocalDatabase, block_external_network
from security_store import SecurityStore
from billing.store import BillingStore
from telegram_bot.assistant import QueHayBot
from security import OWNER_ID


def main():
    block_external_network()
    database = LocalDatabase()
    snapshot = ROOT / '.local/catalog-snapshot.json'
    if snapshot.exists():
        database.rows['contenido'] = json.loads(snapshot.read_text(encoding='utf-8'))
    before = {r['id']: r['descarga'] for r in database.rows['contenido'] if r.get('descarga')}
    accounts = SecurityStore('sqlite:///:memory:', local=True)
    bot = LocalBot()
    messages = []
    bot.send_message = lambda chat_id, text, **kw: messages.append({'text': text, 'markup': json.loads(kw['reply_markup'].to_json()) if kw.get('reply_markup') else {}})
    assistant = QueHayBot(bot, database, accounts, BillingStore(accounts), lambda tid: 0, 'https://cineapp-bot.onrender.com')
    cards = []
    scenarios = [('Menú principal', '/start', 900000005), ('Buscar en el catálogo', '/buscar Naruto', 900000005),
                 ('Acceso del propietario', '/cuenta', OWNER_ID), ('Sin acceso vigente', '/cuenta', 900000005),
                 ('Un solo acceso mensual', '/membresia', 900000005), ('Ayuda y contacto', '/ayuda', 900000005)]
    for title, command, uid in scenarios:
        assistant.handle(SimpleNamespace(text=command, chat=SimpleNamespace(id=uid, type='private'),
                                        from_user=SimpleNamespace(id=uid, first_name='Ale', is_bot=False)))
        response = messages[-1]
        keyboard = response['markup']
        rows = keyboard.get('keyboard') or keyboard.get('inline_keyboard') or []
        buttons = ''.join('<div class="row">' + ''.join('<span class="button">' + escape(button['text']) + '</span>' for button in row) + '</div>' for row in rows)
        cards.append(f'<section><h2>{escape(title)}</h2><div class="bubble">{response["text"].replace(chr(10), "<br>")}</div><div class="keyboard">{buttons}</div></section>')
    html = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QueHay · Revisión del bot</title><style>
    *{box-sizing:border-box}body{margin:0;background:#090f1a;color:#eaf2ff;font:15px/1.6 system-ui,sans-serif;padding:32px}main{max-width:1200px;margin:auto}header{max-width:780px;margin:0 0 30px}h1{font-size:34px;line-height:1.2}h2{font-size:15px;color:#8fc0fa;margin:0 0 16px}.note{color:#a2b3cb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:22px}section{background:#111d30;border:1px solid #293d59;border-radius:20px;padding:22px}.bubble{background:#1c304b;border-radius:14px;padding:18px;font-size:14px}.keyboard{margin-top:12px}.row{display:flex;gap:8px;margin-top:8px}.button{flex:1;text-align:center;background:#233d5c;border:1px solid #365577;border-radius:9px;padding:11px 6px;font-size:13px}footer{color:#a2b3cb;margin-top:24px}@media(max-width:550px){body{padding:16px}h1{font-size:28px}section{padding:16px}}
    </style><main><header><small>QUEHAY · BOT DE TELEGRAM</small><h1>Tu próxima historia empieza aquí.</h1><p class="note">Respuestas generadas por el código del bot con un transporte sin conexión. Esta revisión no envía mensajes a Telegram. Los botones de esta hoja muestran su diseño y texto.</p></header><div class="grid">'''+''.join(cards)+'''</div><footer>Menú de comandos preparado: /start · /catalogo · /buscar · /novedades · /cuenta · /membresia · /ayuda. Botón de apertura: Abrir QueHay.<br>Configuración de Telegram pendiente de aplicar en producción.</footer></main></html>'''
    output = ROOT / '.local/phase17-bot.html'
    output.write_text(html, encoding='utf-8')
    after = {r['id']: r['descarga'] for r in database.rows['contenido'] if r.get('descarga')}
    assert before == after
    result = {'scenarios': len(scenarios), 'manual_downloads_unchanged': len(before),
              'download_digest': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
              'telegram_network_calls': 0, 'production_writes': False}
    (ROOT / '.local/phase17-bot-proof.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    print(str(output))


if __name__ == '__main__':
    main()
