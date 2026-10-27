from concurrent.futures import ThreadPoolExecutor
import pytest
from conftest import register, send, ORIGIN
from services.profiles import Profiles


def devices(system):
    first, second = system.app.test_client(), system.app.test_client()
    csrf1 = register(first).json['csrf_token']
    csrf2 = send(second, '/api/auth/login', {'email': 'person@example.test', 'password': 'Local-user-test-2026!'}).json['csrf_token']
    return first, second, csrf1, csrf2


def test_two_independent_devices_share_avatar_and_list_without_membership(system):
    first, second, csrf1, csrf2 = devices(system)
    assert send(first, '/api/profile', {'action': 'avatar', 'avatar': 'fox'}, csrf1).status_code == 200
    assert send(first, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': True}, csrf1).status_code == 200
    other = send(second, '/api/profile', method='GET').json
    assert other['avatar'] == 'fox' and other['saved_ids'] == [1]
    assert other['items'][0]['has_download'] is True
    assert 'descarga' not in other['items'][0] and 'enlace_canal' not in other['items'][0]
    send(second, '/api/profile', {'action': 'avatar', 'avatar': 'cat'}, csrf2)
    send(second, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': False}, csrf2)
    result = send(first, '/api/profile', method='GET').json
    assert result['avatar'] == 'cat' and result['items'] == [] and result['saved_ids'] == []
    # Profile preferences do not confer membership or alter existing downloads.
    assert send(first, '/api/download/1', method='GET').status_code == 403
    assert system.supabase_service.rows['contenido'][0]['descarga'].endswith('/example/file')


def test_preferences_are_private_and_csrf_protected(system):
    first, second, csrf1, csrf2 = devices(system)
    send(first, '/api/profile', {'action': 'avatar', 'avatar': 'dragon'}, csrf1)
    stranger = system.app.test_client()
    assert send(stranger, '/api/profile', method='GET').status_code == 401
    stranger_csrf = register(stranger, 'different@example.test').json['csrf_token']
    assert send(stranger, '/api/profile', method='GET').json['avatar'] == 'tg'
    assert send(first, '/api/profile', {'action': 'avatar', 'avatar': 'cat'}).status_code == 403
    assert send(first, '/api/profile', {'action': 'avatar', 'avatar': 'cat'}, stranger_csrf).status_code == 403
    # Supplied account IDs are never used to select a different account.
    victim = system.security_store.account(email='person@example.test')['id']
    send(stranger, '/api/profile', {'action': 'avatar', 'avatar': 'cat', 'account_id': victim}, stranger_csrf)
    assert send(first, '/api/profile', method='GET').json['avatar'] == 'dragon'


def test_legacy_import_merges_once_and_cannot_resurrect_deleted_items(system):
    first, second, csrf1, csrf2 = devices(system)
    original = {'action': 'bootstrap', 'avatar': 'wolf', 'saved_ids': [1, 1, 999]}
    result = send(first, '/api/profile', original, csrf1).json
    assert result['avatar'] == 'wolf' and result['saved_ids'] == [1]
    send(first, '/api/profile', {'action': 'avatar', 'avatar': 'cat'}, csrf1)
    send(first, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': False}, csrf1)
    result = send(second, '/api/profile', original, csrf2).json
    assert result['avatar'] == 'cat' and result['saved_ids'] == []
    # An explicit new save may restore a removed item; bootstrap may not.
    result = send(second, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': True}, csrf2).json
    assert result['saved_ids'] == [1]


@pytest.mark.parametrize('body', [
    {'action': 'avatar', 'avatar': 'https://untrusted.example/image.svg'},
    {'action': 'avatar', 'avatar': []}, {'action': 'saved', 'content_id': True, 'saved': True},
    {'action': 'saved', 'content_id': 1, 'saved': 'false'},
    {'action': 'bootstrap', 'saved_ids': [1] * 201}, {'action': 'bootstrap', 'saved_ids': ['1']},
    {'action': 'unknown'},
])
def test_invalid_profile_changes_are_rejected(client, body):
    csrf = register(client).json['csrf_token']
    assert send(client, '/api/profile', body, csrf).status_code == 400


def test_catalog_validation_hidden_items_and_removed_titles(system):
    first, second, csrf1, csrf2 = devices(system)
    assert send(first, '/api/profile', {'action': 'saved', 'content_id': 999, 'saved': True}, csrf1).status_code == 404
    send(first, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': True}, csrf1)
    system.supabase_service.rows['contenido'][0]['disponible'] = False
    assert send(second, '/api/profile', method='GET').json['items'] == []
    assert send(second, '/api/profile', {'action': 'saved', 'content_id': 1, 'saved': False}, csrf2).status_code == 200


def test_concurrent_devices_keep_all_writes_and_enforce_capacity(system):
    account = system.security_store.create_account('Concurrent')['id']
    store = Profiles(system.security_store)
    def save(i):
        store.mutate(account, items=[(i, True)])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(save, range(1, 21)))
    assert len(store.snapshot(account)['saved_ids']) == 20
    store.mutate(account, items=[(i, True) for i in range(21, 201)])
    with pytest.raises(ValueError, match='200'):
        store.mutate(account, items=[(201, True)])
    store.mutate(account, items=[(1, True)])  # Idempotent save does not consume capacity.
    assert len(store.snapshot(account)['saved_ids']) == 200
    store.mutate(account, items=[(1, False), (201, True)])
    assert len(store.snapshot(account)['saved_ids']) == 200
