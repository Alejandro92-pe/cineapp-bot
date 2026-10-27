from types import SimpleNamespace
import pytest
from sqlalchemy import select, update
from services.catalog_jobs import DurableQueue, jobs, CachedTransport
from services.catalog_queue import BatchPause
from conftest import owner_login, send


@pytest.fixture
def queue(system):
    return DurableQueue(system.security_store, clock=lambda: 1000)


class Provider:
    def page(self, resource, page):
        return [{'tmdb_id': 22, 'title': 'Historia'}], {'has_next': False}


def metadata(path, params=None):
    return {'id': 22, 'title': 'Historia', 'vote_average': 8.1, 'release_date': '2026-01-01'}


def test_discovery_persists_and_does_not_duplicate(queue, system):
    queue.discover(Provider(), 'movies')
    other = DurableQueue(system.security_store, clock=lambda: 1001)
    assert other.summary() == {'pending': 1}
    assert other.discover(Provider(), 'movies') == 0
    queue.set_setting('finished:movies', 0)
    queue.discover(Provider(), 'movies')
    assert queue.summary() == {'pending': 1}


def test_complete_movie_published_once_and_keeps_rating(queue):
    published = []
    result = queue.run(Provider(), metadata, published.append)
    assert result['imported'] == 1 and result['queue'] == {'done': 1}
    assert published[0]['contenido']['rating'] == 8.1
    assert published[0]['contenido']['tmdb_media'] == 'movie'
    assert queue.run(Provider(), metadata, published.append)['waiting'] is True
    queue.set_setting('batch_after', 0)
    queue.run(Provider(), metadata, published.append, discover=False)
    assert len(published) == 1


def test_bad_discovery_page_does_not_block_pending_titles(queue):
    queue.discover(Provider(), 'movies')
    queue.set_setting('finished:movies', 0)
    class BrokenProvider:
        def page(self, resource, page):
            raise RuntimeError('provider token=PRIVATE')
    published = []
    result = queue.run(BrokenProvider(), metadata, published.append)
    assert result['discovery_review'] is True and result['imported'] == 1
    assert queue.get_setting('turn') == 1
    assert queue.get_setting('page:movies') == 1
    assert 'PRIVATE' not in str(result)
    assert len(published) == 1


def test_interrupted_job_recovers_without_publishing_partial_title(queue):
    queue.discover(Provider(), 'movies')
    with queue.engine.begin() as c: c.execute(update(jobs).values(status='running'))
    def paused(*a): raise BatchPause()
    published = []
    assert queue.run(Provider(), paused, published.append, discover=False)['paused'] is True
    assert published == [] and queue.summary() == {'pending': 1}
    queue.clock = lambda: 2000
    assert queue.run(Provider(), metadata, published.append, discover=False)['imported'] == 1


def test_failures_are_bounded_and_do_not_save_secrets(queue):
    queue.discover(Provider(), 'movies')
    def broken(*a): raise RuntimeError('token=PRIVATE')
    for i in range(3):
        queue.clock = lambda i=i: 10000*(i+1)
        assert queue.run(Provider(), broken, lambda d: None, discover=False)['review'] is True
    assert queue.summary() == {'failed': 1}
    with queue.engine.connect() as c: assert 'PRIVATE' not in c.execute(select(jobs.c.note)).scalar_one()


def test_concurrent_batch_does_not_run(queue):
    with queue.lock() as acquired:
        assert acquired
        assert queue.run(Provider(), metadata, lambda d: None) == {'busy': True}


def test_cached_provider_response_resumes_without_network_and_obeys_deadline(queue):
    calls = []
    session = SimpleNamespace(get=lambda url, **kw: calls.append(url) or SimpleNamespace(status_code=200, json=lambda: {'data': [1]}, headers={}))
    transport = CachedTransport(queue, session=session, clock=lambda: 1000)
    assert transport.get('https://provider.example/list', params={'api_key': 'private'}).json() == {'data': [1]}
    second = CachedTransport(queue, session=session, clock=lambda: 1000)
    assert second.get('https://provider.example/list', params={'api_key': 'private'}).json() == {'data': [1]}
    assert len(calls) == 1
    second.deadline = 1002
    with pytest.raises(BatchPause): second.get('https://provider.example/another')


def test_queue_status_owner_only_and_local_disabled(client):
    assert send(client, '/api/admin/catalog/queue', method='GET').status_code == 403
    csrf = owner_login(client).json['csrf_token']
    response = send(client, '/api/admin/catalog/queue', method='GET')
    assert response.status_code == 200 and response.json == {'enabled': False, 'configured': False, 'queue': {}}
    assert send(client, '/api/admin/catalog/queue/settings', {'enabled': False}, csrf).status_code == 200
    assert send(client, '/api/admin/catalog/queue/settings', {'enabled': 'yes'}, csrf).status_code == 400
