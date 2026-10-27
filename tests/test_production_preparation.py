import os
from types import SimpleNamespace
from conftest import send
from services.catalog_aliases import resolve_alias


def test_persistent_alias_resolution_preserves_season():
    class Query:
        def select(self, fields): return self
        def eq(self, field, value):
            assert (field, value) == ('original_id', 405)
            return self
        def execute(self): return SimpleNamespace(data=[{'content_id': 404, 'start_season': 2}])
    database = SimpleNamespace(table=lambda name: Query() if name == 'catalog_aliases' else None)
    assert resolve_alias(database, 405) == {'id': 404, 'start_season': 2}


def test_stable_telegram_webhook_requires_the_provider_secret(client, system):
    assert send(client, '/webhook/telegram', {'update_id': 1}).status_code == 401
    assert not system.bot.calls
    result = send(client, '/webhook/telegram', {'update_id': 1}, headers={
        'X-Telegram-Bot-Api-Secret-Token': os.environ['TELEGRAM_WEBHOOK_SECRET']})
    assert result.status_code == 200
    assert system.bot.calls == ['process_new_updates']


def test_telegram_configuration_preserves_pending_updates():
    from scripts.configure_telegram_production import configure
    from local_support import LocalBot
    class Bot(LocalBot):
        def set_webhook(self, **kwargs):
            assert kwargs['drop_pending_updates'] is False
            assert kwargs['secret_token'] == 'x'*40
            self.url = kwargs['url']; return True
        def get_webhook_info(self): return SimpleNamespace(url=self.url, pending_update_count=0)
        def get_my_commands(self, **kw): return [SimpleNamespace(command='start')]
        def get_chat_menu_button(self): return SimpleNamespace(text='Abrir QueHay')
    result = configure(Bot(), 'https://quehay.example', 'x'*40)
    assert result['webhook'] == 'https://quehay.example/webhook/telegram'
    assert result['menu'] == 'Abrir QueHay'
