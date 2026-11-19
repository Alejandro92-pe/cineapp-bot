"""The archive password shown before a download depends on the site hosting the file."""
import pytest
from services.download_passwords import DEFAULT, clean, password_for, load, save, KEY, FOREVER
from conftest import send, owner_login, register, tg_login


@pytest.mark.parametrize('url,password', [
    ('https://drive.google.com/file/d/abc/view', 'quehay.live'),
    ('https://docs.google.com/uc?id=abc', 'quehay.live'),
    ('https://www.mediafire.com/file/x/peli.rar/file', 'cc'),
    ('https://megaup.net/abc/peli.rar', ''),
    ('https://ejemplo.com/peli.torrent', ''),
    ('https://www.1337torrents.to/peli', ''),
    ('https://pixeldrain.com/u/abc', 'cc'),
])
def test_default_rules(url, password):
    assert password_for(url, DEFAULT) == password


def test_lookalike_domains_do_not_borrow_a_rule():
    assert password_for('https://mediafire.com.evil.test/x', DEFAULT) == 'cc'        # default, not the MediaFire rule
    assert password_for('https://notdrive.google.com.evil.test/x', DEFAULT) == 'cc'
    assert password_for('https://megaup.net.evil.test/x', DEFAULT) == 'cc'


@pytest.mark.parametrize('bad', [{'rules': 'x'}, {'rules': [{'site': 'https://mediafire.com/', 'password': 'cc'}]},
                                 {'rules': [{'site': 'a.com', 'password': 'x' * 101}]},
                                 {'rules': [{'site': 'a.com'}, {'site': 'A.com'}]}])
def test_invalid_rules_are_rejected(bad):
    with pytest.raises(ValueError):
        clean(bad)


def test_rules_survive_cache_cleanup_and_are_owner_only(client, system):
    from sqlalchemy import select, delete
    from services.catalog_jobs import cache
    auth = register(client)
    body = {'rules': [{'site': 'www.MediaFire.com', 'password': 'nueva'}, {'site': '', 'password': ''}], 'default': 'otra'}
    assert send(client, '/api/admin/download-passwords', body, auth.json['csrf_token']).status_code == 403
    admin = system.app.test_client(); owner = owner_login(admin)
    saved = send(admin, '/api/admin/download-passwords', body, owner.json['csrf_token']).json
    assert saved == {'rules': [{'site': 'mediafire.com', 'password': 'nueva'}], 'default': 'otra'}
    engine = system.security_store.engine
    with engine.begin() as c:   # what the catalog clean-up runs
        c.execute(delete(cache).where(cache.c.expires < 4102444800))
    assert load(engine) == saved
    assert send(admin, '/api/admin/download-passwords', {'rules': [{'site': 'x', 'password': ''}]}, owner.json['csrf_token']).status_code == 400


def test_movie_and_episode_downloads_carry_the_password(client, system):
    tg_login(client)
    movie = send(client, '/api/download/1', method='GET').json
    assert movie['host'] == 'www.mediafire.com' and movie['password'] == 'cc'
    save(system.security_store.engine, True, {'rules': [{'site': 'mediafire.com', 'password': ''}], 'default': 'cc'})
    assert send(client, '/api/download/1', method='GET').json['password'] == ''
