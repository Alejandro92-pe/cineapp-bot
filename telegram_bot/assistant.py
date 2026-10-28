"""Private-chat navigation. Watching, downloads and payments remain in the web app."""
from datetime import datetime, timedelta, timezone
from html import escape
import re
import time
import unicodedata

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, WebAppInfo
from security import OWNER_ID

COMMANDS = [
    ('start', 'Abrir el menú de QueHay'), ('catalogo', 'Explorar películas, series y anime'),
    ('buscar', 'Buscar un título'), ('novedades', 'Últimos títulos añadidos'),
    ('cuenta', 'Consultar mi acceso'), ('membresia', 'Acceso mensual y formas de pago'),
    ('ayuda', 'Reproducción, descargas y soporte'),
]
MENU_ROWS = [('🎬 Ver catálogo', '🔎 Buscar'), ('✨ Novedades', '👤 Mi cuenta'),
             ('🎟 Acceso mensual', '💬 Ayuda')]
RETIRED = {'activar', 'auto_activar', 'reactivar', 'desactivar', 'generar_enlaces', 'activos'}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if unicodedata.category(c) != 'Mn').strip()


class QueHayBot:
    def __init__(self, bot, catalog, accounts, billing, legacy_expiry, origin, publish=None):
        self.bot, self.catalog, self.accounts, self.billing = bot, catalog, accounts, billing
        self.legacy_expiry, self.origin, self.publish = legacy_expiry, origin.rstrip('/'), publish

    def link(self, label, path=''):
        return InlineKeyboardButton(label, web_app=WebAppInfo(url=self.origin + path))

    def keyboard(self, *buttons):
        return InlineKeyboardMarkup(row_width=1).add(*buttons)

    def send(self, chat_id, text, markup=None):
        self.bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup,
                              disable_web_page_preview=True)

    def menu(self, chat_id, name=''):
        markup = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True,
            input_field_placeholder='Busca un título o elige una opción')
        for row in MENU_ROWS:
            markup.row(*row)
        self.send(chat_id, f'🍿 <b>¡Hola{", " + escape(name[:60]) if name else ""}! Estás en QueHay.</b>\n\n'
                  'Encuentra tu próxima historia. Puedes explorar gratis; para reproducir y descargar necesitas acceso vigente.\n\n'
                  'Elige una opción o escríbeme el nombre de una película, serie o anime.', markup)

    def access(self, telegram_id):
        # Resolve the sender, never a chat parameter or Flask administrator session.
        if telegram_id == OWNER_ID:
            return {'permanent': True, 'expires_at': 0, 'active': True}
        account = self.accounts.account(telegram_id=telegram_id)
        end = max(self.billing.expiry(account['id']) if account else 0,
                  self.legacy_expiry(telegram_id))
        return {'permanent': False, 'expires_at': end, 'active': end > time.time()}

    def account(self, user_id):
        status = self.access(user_id)
        if status['permanent']:
            text = '👤 <b>Tu cuenta · Propietario</b>\nAcceso permanente. No necesitas comprar una membresía.'
        elif status['active']:
            end = datetime.fromtimestamp(status['expires_at'], timezone(timedelta(hours=-5)))
            text = f'👤 <b>Tu acceso está activo</b>\nDisponible hasta el {end:%d/%m/%Y a las %H:%M} (hora de Perú).\nSin renovación automática.'
        else:
            text = '👤 <b>Tu cuenta</b>\nNo encuentro acceso vigente vinculado a este Telegram. Puedes explorar el catálogo e iniciar sesión gratis.\n\nSi compraste con otra cuenta, entra con ella en Mi cuenta y vincula tu Telegram.'
        self.send(user_id, text, self.keyboard(self.link('👤 Abrir mi cuenta', '/cuenta'),
                  self.link('🎬 Ver catálogo') if status['active'] else self.link('🎟 Conocer el acceso', '/membresia')))

    def membership(self, chat_id):
        self.send(chat_id, '🎟 <b>Un solo acceso · 30 días</b>\n\n'
                  '• Buy Me a Coffee: <b>US$1.50</b>\n• Yape / Plin: <b>S/5.50</b>\n• Binance Pay: <b>1.50 USDT</b>\n\n'
                  'Un pago, sin renovación automática. Buy Me a Coffee confirma automáticamente; los pagos con QR se revisan manualmente.\n\n'
                  'Empieza desde la página de acceso para asociar el pago a tu cuenta. Allí puedes consultar su estado.',
                  self.keyboard(self.link('Conocer el acceso mensual', '/membresia')))

    def catalog_rows(self, query='', limit=6):
        rows = self.catalog.table('contenido').select('id,titulo,tipo,año,rating').eq('disponible', True)
        if query:
            # Remove PostgREST pattern metacharacters; do not interpolate filter expressions.
            query = re.sub(r'[^\w\s\-áéíóúüñ]', ' ', query, flags=re.UNICODE).strip()[:80]
            if len(query) < 2:
                return []
            rows = rows.ilike('titulo', '%' + query + '%')
        return rows.order('id', desc=True).limit(limit).execute().data or []

    def results(self, chat_id, query=None):
        if query is not None and len(query.strip()) < 2:
            self.send(chat_id, '🔎 Escribe al menos dos letras del título. Por ejemplo: /buscar Naruto')
            return
        rows = self.catalog_rows(query or '')
        if not rows:
            self.send(chat_id, 'No encontré títulos disponibles. Prueba con una parte del nombre o explora el catálogo.',
                      self.keyboard(self.link('🎬 Explorar catálogo')))
            return
        heading = f'🔎 <b>Resultados para {escape(query[:80])}</b>' if query is not None else '✨ <b>Recién añadidos a QueHay</b>'
        lines, buttons = [], []
        for index, row in enumerate(rows, 1):
            title = str(row.get('titulo') or 'Sin título')[:100]
            kind = {'pelicula': 'Película', 'serie': 'Serie', 'anime': 'Anime', 'biblico': 'Bíblico'}.get(row.get('tipo'), 'Título')
            lines.append(f'{index}. <b>{escape(title)}</b> · {kind}')
            buttons.append(self.link(f'{index}. {title[:48]}', f'/?contenido={int(row["id"])}'))
        self.send(chat_id, heading + '\n\n' + '\n'.join(lines) + '\n\nAbre una ficha para ver sus episodios y descargas.', self.keyboard(*buttons))

    def help(self, chat_id):
        self.send(chat_id, '💬 <b>¿En qué te ayudo?</b>\n\n'
                  '▶️ <b>Reproducir:</b> abre la ficha y pulsa Play. En series y anime, elige el episodio.\n'
                  '📥 <b>Descargar:</b> pulsa Descargar en la película o en cada episodio que tenga enlace. Si Telegram no abre el proveedor, abre la página en tu navegador.\n'
                  '🎟 <b>Pagos:</b> revisa el estado en Acceso mensual. No envíes comprobantes aquí: registra el pago en esa página.\n'
                  '📺 El reproductor puede incluir publicidad de terceros.\n\n'
                  'Para un problema o sugerir un título, contacta con Ale. Indica el título y el episodio; no compartas contraseñas.',
                  self.keyboard(self.link('Consultar mi pago', '/membresia'),
                                self.link('Instalar en Android', '/instalar'),
                                InlineKeyboardButton('Hablar con Ale', url='https://t.me/aleDesigner18')))

    def register_user(self, user):
        if not self.catalog.table('usuarios').select('id').eq('telegram_id', user.id).execute().data:
            self.catalog.table('usuarios').insert({'telegram_id': user.id, 'nombre': str(user.first_name or '')[:80], 'membresia_activa': False}).execute()

    def handle(self, message):
        if message.chat.type != 'private' or message.chat.id != message.from_user.id or message.from_user.is_bot:
            return
        uid = message.from_user.id
        if not self.accounts.allow_attempt(f'bot:{uid}', 60):
            return
        try:
            self.dispatch(message)
        except Exception:
            # Do not leak service URLs, credentials or user-supplied exception text.
            self.send(uid, 'No pude completar la consulta. Puedes continuar en QueHay.', self.keyboard(self.link('Abrir QueHay')))

    def dispatch(self, message):
        uid = message.from_user.id
        if not message.text:
            self.send(uid, 'Los comprobantes se registran en Acceso mensual. Si necesitas ayuda, contacta con Ale desde Ayuda.',
                      self.keyboard(self.link('Registrar o consultar mi pago', '/membresia'),
                                    InlineKeyboardButton('Ayuda', callback_data='qh:ayuda')))
            return
        text = message.text.strip()[:200]
        parts = text.split(maxsplit=1)
        command = parts[0].split('@')[0].lstrip('/').lower() if parts else ''
        arg = parts[1] if text.startswith('/') and len(parts) > 1 else ''
        action = normalized(text)
        if text.startswith('/'):
            action = command
        labels = {'🎬 ver catalogo': 'catalogo', '📱 mini app vip': 'catalogo', '🔎 buscar': 'buscar',
                  '✨ novedades': 'novedades', '👤 mi cuenta': 'cuenta', '🎟 acceso mensual': 'membresia',
                  '💬 ayuda': 'ayuda', '🆘 ayuda': 'ayuda', '💰 como pagar': 'membresia',
                  '🎬 beneficios vip': 'membresia', '⭐ testimonios': 'membresia',
                  'planes': 'membresia', 'ver planes': 'membresia', 'precio': 'membresia',
                  'hola': 'menu', 'ayuda': 'ayuda', 'soporte': 'ayuda', 'descargas': 'ayuda', 'sugerir': 'ayuda'}
        action = labels.get(action, action)
        if command == 'start' and text.startswith('/'):
            self.register_user(message.from_user)
            self.menu(uid, message.from_user.first_name or '')
            if arg in {'planes', 'membresia'} or arg.startswith('pago_'):
                return self.membership(uid)
            if arg == 'miniapp':
                action = 'catalogo'
            elif re.fullmatch(r'contenido_\d{1,12}', arg):
                cid = int(arg.split('_')[1])
                rows = self.catalog.table('contenido').select('id,titulo').eq('id', cid).eq('disponible', True).execute().data
                if rows:
                    return self.send(uid, '🎬 <b>' + escape(str(rows[0]['titulo'])[:100]) + '</b>', self.keyboard(self.link('Abrir ficha', f'/?contenido={cid}')))
                return self.send(uid, 'Este título ya no está disponible.', self.keyboard(self.link('Ver catálogo')))
            else:
                return
        if action in RETIRED:
            if uid == OWNER_ID:
                self.send(uid, 'La gestión de pagos y accesos se realiza en el panel. Los accesos a canales están retirados.', self.keyboard(self.link('Abrir panel', '/admin')))
            else:
                self.membership(uid)
        elif action == 'publicar':
            if uid != OWNER_ID:
                return self.send(uid, 'Esta opción es solo para el administrador.')
            if not arg.isdigit() or not self.publish:
                return self.send(uid, 'Usa /publicar ID_CONTENIDO para anunciar una ficha en los canales de marketing.')
            rows = self.catalog.table('contenido').select('*').eq('id', int(arg)).eq('disponible', True).execute().data
            if not rows:
                return self.send(uid, 'No encontré ese título disponible.')
            self.send(uid, 'Publicación enviada.' if self.publish(rows[0]) else 'No se pudo completar la publicación.')
        elif action in {'menu', 'cancelar'}:
            self.menu(uid, message.from_user.first_name or '')
        elif action in {'catalogo', 'miniapp'}:
            self.send(uid, '🎬 <b>Tu próxima historia está en QueHay</b>\nPelículas, series, anime y bíblicos. Abre el catálogo y elige qué ver.', self.keyboard(self.link('🎬 Abrir QueHay')))
        elif action == 'buscar':
            self.results(uid, arg)
        elif action == 'novedades':
            self.results(uid)
        elif action == 'cuenta':
            self.account(uid)
        elif action in {'membresia', 'pagar'}:
            self.membership(uid)
        elif action == 'ayuda':
            self.help(uid)
        elif action == 'instalar':
            self.send(uid, 'Lleva QueHay en tu Android. Abre esta página en Chrome y sigue los pasos.', self.keyboard(self.link('Instalar QueHay', '/instalar')))
        elif text.startswith('/'):
            self.send(uid, 'Usa /menu para ver las opciones, /buscar seguido de un título o /ayuda.')
        else:
            self.results(uid, text)

    def callback(self, call):
        message = getattr(call, 'message', None)
        if not message or message.chat.type != 'private' or message.chat.id != call.from_user.id:
            return self.bot.answer_callback_query(call.id, 'Abre el bot en privado.')
        self.bot.answer_callback_query(call.id)
        if not self.accounts.allow_attempt(f'bot:{call.from_user.id}', 60):
            return
        if call.data == 'qh:ayuda':
            self.help(call.from_user.id)
        else:
            # Existing Telegram messages cannot be recalled; old payment callbacks stay safe.
            self.membership(call.from_user.id)

    def register(self):
        self.bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'],
                                 func=lambda m: m.chat.type == 'private')(self.handle)
        self.bot.callback_query_handler(func=lambda call: True)(self.callback)
        return self
