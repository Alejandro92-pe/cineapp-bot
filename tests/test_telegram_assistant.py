import copy
import json
import time
from types import SimpleNamespace

import pytest
from telebot import TeleBot
from telebot.types import Message, Update

from conftest import send, owner_login, register
from security import OWNER_ID
from telegram_bot.assistant import QueHayBot, MENU_ROWS


def message(text='/start', uid=900000005, chat_type='private', content=None):
    data = {'message_id': 123, 'date': int(time.time()), 'chat': {'id': uid, 'type': chat_type},
            'from': {'id': uid, 'is_bot': False, 'first_name': '<Ale&>'}}
    if content:
        data.update(content)
    else:
        data['text'] = text
    return Message.de_json(data)


@pytest.fixture
def assistant(system):
    # Real pyTelegramBotAPI dispatch, with every outbound operation replaced locally.
    bot = TeleBot('123456:TEST_ONLY_TOKEN', threaded=False)
    bot.sent = []
    bot.answers = []
    bot.send_message = lambda chat_id, text, **kw: bot.sent.append({'chat_id': chat_id, 'text': text, **kw})
    bot.answer_callback_query = lambda *args, **kw: bot.answers.append((args, kw))
    service = QueHayBot(bot, system.supabase_service, system.security_store, system.billing_store,
                       system.legacy_access_expiry, 'https://quehay.example').register()
    return service


def process(service, text='/start', **kw):
    msg = message(text, **kw)
    service.bot.process_new_updates([Update.de_json({'update_id': 1, 'message': msg.json})])
    return service.bot.sent[-1] if service.bot.sent else None


def buttons(response):
    return json.loads(response['reply_markup'].to_json())


def test_actual_dispatch_new_six_button_menu(assistant, system):
    response = process(assistant)
    assert '<Ale&>' not in response['text'] and '&lt;Ale&amp;&gt;' in response['text']
    assert [[b['text'] for b in row] for row in buttons(response)['keyboard']] == [list(row) for row in MENU_ROWS]
    assert buttons(response)['is_persistent'] is True
    assert system.supabase_service.table('usuarios').select('*').eq('telegram_id', 900000005).execute().data
    process(assistant)
    assert len(system.supabase_service.table('usuarios').select('*').eq('telegram_id', 900000005).execute().data) == 1


@pytest.mark.parametrize('text', ['/membresia', '/start planes', '/start pago_copper', '💰 Cómo pagar', '⭐ Testimonios'])
def test_old_payment_buttons_open_only_current_monthly_flow(assistant, text):
    response = process(assistant, text)
    assert all(value in response['text'] for value in ('US$1.50', 'S/5.50', '1.50 USDT', 'sin renovación automática'))
    assert buttons(response)['inline_keyboard'][0][0]['web_app']['url'].endswith('/membresia')
    assert not any(old in response['text'] for old in ('50%', 'copper', 'tutorial', 'PayPal'))


def test_search_and_recent_only_available_no_download_leak(assistant, system):
    rows = system.supabase_service.rows['contenido']
    rows.extend([{'id': 2, 'titulo': 'Naruto <especial>', 'tipo': 'anime', 'disponible': True, 'descarga': 'https://secret.example/file'},
                 {'id': 3, 'titulo': 'Naruto oculto', 'disponible': False}])
    before = copy.deepcopy(rows)
    response = process(assistant, '/buscar Naruto')
    assert 'Naruto &lt;especial&gt;' in response['text'] and 'oculto' not in response['text']
    assert buttons(response)['inline_keyboard'][0][0]['web_app']['url'] == 'https://quehay.example/?contenido=2'
    assert 'secret.example' not in str(response)
    assert 'Naruto &lt;especial&gt;' in process(assistant, 'Naruto')['text']
    assert 'Recién añadidos' in process(assistant, '/novedades')['text']
    assert rows == before


def test_search_bound_and_empty_help(assistant, system):
    assert 'al menos dos' in process(assistant, '🔎 Buscar')['text']
    assert 'No encontré' in process(assistant, '/buscar %*,)')['text']
    system.supabase_service.rows['contenido'] = [{'id': i, 'titulo': f'Película {i}', 'disponible': True} for i in range(1, 30)]
    assert len(buttons(process(assistant, '/novedades'))['inline_keyboard']) == 6


def test_deep_link_and_old_miniapp(assistant):
    response = process(assistant, '/start contenido_1')
    assert buttons(response)['inline_keyboard'][0][0]['web_app']['url'].endswith('/?contenido=1')
    assert 'ya no está disponible' in process(assistant, '/start contenido_999')['text']
    assert buttons(process(assistant, '/start miniapp'))['inline_keyboard'][0][0]['web_app']['url'] == 'https://quehay.example'


def test_owner_permanent_but_sender_identity_never_argument(assistant):
    assert 'Acceso permanente' in process(assistant, '/cuenta', uid=OWNER_ID)['text']
    response = process(assistant, f'/cuenta {OWNER_ID}')
    assert 'No encuentro acceso vigente' in response['text']


def test_expiry_uses_both_stores_and_not_admin_flask_session(assistant, system, client, monkeypatch):
    account = system.security_store.create_account('Usuario', telegram_id=900000005)
    monkeypatch.setattr(system.billing_store, 'expiry', lambda aid: time.time() + 86400 if aid == account['id'] else 0)
    assert 'Tu acceso está activo' in process(assistant, '/cuenta')['text']
    owner_login(client)
    with system.app.test_request_context('/'):
        from flask import g
        g.identity = {'account': {'telegram_id': OWNER_ID}}
        assert assistant.access(999999999)['active'] is False
    assert 'Tu acceso está activo' in process(assistant, '/cuenta', uid=900000001)['text']
    monkeypatch.setattr(system.billing_store, 'expiry', lambda aid: time.time()-1)
    assert 'No encuentro acceso vigente' in process(assistant, '/cuenta')['text']


def test_group_and_forged_sender_have_no_response(assistant):
    assert process(assistant, '/cuenta', chat_type='group') is None
    msg = message('/cuenta'); msg.chat.id = OWNER_ID
    assistant.handle(msg)
    assert not assistant.bot.sent


@pytest.mark.parametrize('command', ['activar 123 copper', 'auto_activar 123 diamond', 'reactivar 123 gold', 'desactivar 123', 'generar_enlaces 123', 'activos'])
def test_retired_admin_commands_do_not_modify_data(assistant, system, command):
    before = copy.deepcopy(system.supabase_service.rows)
    response = process(assistant, '/' + command, uid=OWNER_ID)
    assert 'canales están retirados' in response['text']
    assert system.supabase_service.rows == before and system.bot.calls == []


def test_support_requires_explicit_contact_no_forwarding(assistant):
    response = process(assistant, '/ayuda')
    assert any(row[0].get('url') == 'https://t.me/aleDesigner18' for row in buttons(response)['inline_keyboard'])
    assert 'registran' in process(assistant, content={'photo': [{'file_id': 'photo', 'file_unique_id': 'x', 'width': 1, 'height': 1}]})['text']
    assert all(sent['chat_id'] == 900000005 for sent in assistant.bot.sent)


def test_old_callback_cannot_cancel_or_grant_payment(assistant, system):
    before = copy.deepcopy(system.supabase_service.rows)
    for data in ('cancelar_voucher', 'plan_gold', 'pago_soles_general'):
        assistant.callback(SimpleNamespace(id='cb', data=data, message=message(), from_user=message().from_user))
    assert len(assistant.bot.answers) == 3
    assert system.supabase_service.rows == before
    assert all('US$1.50' in row['text'] for row in assistant.bot.sent)


def test_publish_owner_only_and_available(assistant, system):
    published = []
    assistant.publish = lambda row: published.append(row) or True
    assert 'administrador' in process(assistant, '/publicar 1')['text']
    assert not published
    assert 'enviada' in process(assistant, '/publicar 1', uid=OWNER_ID)['text']
    assert len(published) == 1
    assert 'No encontré' in process(assistant, '/publicar 999', uid=OWNER_ID)['text']
    assert system.construir_botones_canal({'id': 1}).to_dict()['inline_keyboard'][0][0]['url'].endswith('?start=contenido_1')


def test_bot_rate_limit_and_unavailable_service(assistant, monkeypatch):
    monkeypatch.setattr(assistant.accounts, 'allow_attempt', lambda *a: False)
    assert process(assistant) is None
    monkeypatch.setattr(assistant.accounts, 'allow_attempt', lambda *a: True)
    def unavailable(*a, **kw): raise RuntimeError('private-secret')
    monkeypatch.setattr(assistant, 'catalog_rows', unavailable)
    response = process(assistant, '/novedades')
    assert 'No pude completar' in response['text'] and 'private-secret' not in response['text']


def test_expiry_cron_never_bans_or_contacts_old_members(system):
    before = copy.deepcopy(system.supabase_service.rows)
    system.supabase_service.rows['usuarios'][0]['fecha_vencimiento'] = '2000-01-01T00:00:00+00:00'
    system.verificar_vencimientos()
    import marketing
    assert marketing.recordatorio_pagos_pendientes()['enabled'] is False
    assert not system.bot.calls
    assert system.supabase_service.rows['usuarios'][0]['membresia_activa'] is True


def test_legacy_approval_retired_and_marketing_does_not_target_new_paid_account(system, client, monkeypatch):
    csrf = owner_login(client).json['csrf_token']
    assert send(client, '/aprobar_pago', {'pagoId': 1}, csrf).status_code == 410
    import marketing
    system.supabase_service.rows['usuarios'].extend([
        {'id': 2, 'telegram_id': OWNER_ID, 'membresia_activa': False},
        {'id': 3, 'telegram_id': 900000005, 'membresia_activa': False}])
    account = system.security_store.create_account('Paid', telegram_id=900000005)
    monkeypatch.setattr(system.billing_store, 'expiry', lambda aid: time.time() + 1000 if aid == account['id'] else 0)
    assert marketing.obtener_usuarios_sin_pago() == []


def test_deployment_menu_configuration_is_explicit_and_offline():
    from scripts.configure_bot_menu import menu_configuration, apply_configuration
    config = menu_configuration('https://quehay.example/')
    assert config['menu_button']['web_app']['url'] == 'https://quehay.example'
    assert len(config['commands']) == 7
    with pytest.raises(ValueError): menu_configuration('https://user:pass@quehay.example')
    calls = []
    fake = SimpleNamespace(set_my_commands=lambda *a, **kw: calls.append(('commands', a, kw)),
                           set_chat_menu_button=lambda **kw: calls.append(('menu', kw)))
    apply_configuration(fake, config)
    assert len(calls) == 8

def test_webhook_dispatches_real_menu_and_owner_account(client, system, assistant, monkeypatch):
    import os
    monkeypatch.setattr(system, 'bot', assistant.bot)
    headers={'X-Telegram-Bot-Api-Secret-Token':os.environ['TELEGRAM_WEBHOOK_SECRET']}
    for i,text in enumerate(('/start','/cuenta')):
        response=send(client,'/webhook/telegram',{'update_id':100+i,'message':message(text,uid=OWNER_ID).json},headers=headers)
        assert response.status_code==200
    assert buttons(assistant.bot.sent[0])['is_persistent'] is True
    assert 'Acceso permanente' in assistant.bot.sent[-1]['text']
