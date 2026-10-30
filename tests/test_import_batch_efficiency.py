"""Local regressions for timer reuse and durable, bounded checkpoints."""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import event, select

from services.catalog_jobs import DurableQueue, CachedTransport
from services.catalog_queue import BatchPause
from services.videoapi_jobs import VideoAPIQueue, jobs
from test_videoapi_import import Provider, metadata


class Clock:
    value = 1000
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += seconds


@contextmanager
def statements(engine):
    captured = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        captured.append((statement, parameters))
    event.listen(engine, 'before_cursor_execute', capture)
    try: yield captured
    finally: event.remove(engine, 'before_cursor_execute', capture)


def checkpoints(captured):
    return [sql for sql, _ in captured if sql.startswith('UPDATE') and 'SET source=' in sql]


def gate_reads(captured):
    return [sql for sql, params in captured if sql.startswith('SELECT')
            and 'catalog_settings.value' in sql and any(str(p).endswith('next_request') for p in params)]


def response(status=200, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {}, json=lambda: {'ok': True})


def test_gate_read_once_per_lock_and_reservations_persist_before_http(system):
    clock = Clock(); q = DurableQueue(system.security_store, clock)
    observer = DurableQueue(system.security_store, clock)
    calls = []
    def request(url, **kwargs):
        # Separate queue instance reads storage, not the batch's in-memory gate.
        assert observer.get_setting('next_request') == clock() + 1.5
        calls.append(clock())
        return response()
    transport = CachedTransport(q, seconds=1.5, max_seconds=18, session=SimpleNamespace(get=request),
                                clock=clock, sleep=clock.sleep)
    with statements(q.engine) as captured:
        with q.lock() as acquired:
            assert acquired
            transport.get('https://fixture/1'); transport.get('https://fixture/2')
            # A competing attempt must not erase the owner's timer cache.
            with q.lock() as competing: assert not competing
            transport.get('https://fixture/3')
    assert calls == [1000, 1001.5, 1003]
    assert len(gate_reads(captured)) == 4  # One batch read + three observer reads.
    # New owner/next batch observes an external backoff even if transport reused.
    observer.set_setting('next_request', 1100)
    with q.lock():
        with pytest.raises(BatchPause): transport.get('https://fixture/4')
    assert len(calls) == 3
    assert q.get_setting('next_request') == 1100


def test_unlocked_timer_never_reuses_stale_value_and_namespaces_isolated(system):
    q = DurableQueue(system.security_store); other = DurableQueue(system.security_store)
    assert q.get_setting('next_request') == 0
    other.set_setting('next_request', 2000)
    assert q.get_setting('next_request') == 2000
    video = VideoAPIQueue(system.security_store)
    with video.lock():
        assert video.get_setting('next_request') == 0
        video.set_setting('next_request', 3000)
        assert video.get_setting('next_request') == 3000
    assert q.get_setting('next_request') == 2000


@pytest.mark.parametrize('failure,delay', [('rate', 120), ('server', 60), ('network', 30)])
def test_backoff_survives_release_restart_and_cache_hits(system, failure, delay):
    clock = Clock(); q = DurableQueue(system.security_store, clock); calls = []
    def request(url, **kwargs):
        calls.append(url)
        if failure == 'network': raise requests.ConnectionError('fixture')
        return response(429 if failure == 'rate' else 503,
                        {'Retry-After': '120'} if failure == 'rate' else {})
    transport = CachedTransport(q, session=SimpleNamespace(get=request), clock=clock, sleep=clock.sleep)
    with q.lock():
        with pytest.raises(BatchPause): transport.get('https://fixture/error')
    restarted = DurableQueue(system.security_store, clock)
    assert restarted.get_setting('next_request') == 1000 + delay
    retry = CachedTransport(restarted, max_seconds=18, session=SimpleNamespace(get=request),
                            clock=clock, sleep=clock.sleep)
    with restarted.lock():
        with pytest.raises(BatchPause): retry.get('https://fixture/another')
    assert len(calls) == 1


def test_cached_response_does_not_read_or_advance_timer(system):
    clock = Clock(); q = DurableQueue(system.security_store, clock)
    transport = CachedTransport(q, session=SimpleNamespace(get=lambda *a, **k: response()),
                                clock=clock, sleep=clock.sleep)
    with q.lock(): transport.get('https://fixture/cached')
    before = q.get_setting('next_request')
    with statements(q.engine) as captured:
        with q.lock(): transport.get('https://fixture/cached')
    assert not gate_reads(captured)
    assert q.get_setting('next_request') == before and transport.requests == 1


def test_failed_reservation_cannot_issue_request(system, monkeypatch):
    q = DurableQueue(system.security_store); calls = []
    transport = CachedTransport(q, session=SimpleNamespace(get=lambda *a, **k: calls.append(a)))
    def fail(*args): raise RuntimeError('reservation unavailable')
    monkeypatch.setattr(q, 'set_setting', fail)
    with q.lock():
        with pytest.raises(RuntimeError): transport.get('https://fixture/new')
    assert calls == []


@pytest.mark.parametrize('failure', ['pause', 'error', 'interrupt'])
def test_partial_batch_saves_once_and_restart_reuses_validated_progress(system, failure):
    q = VideoAPIQueue(system.security_store, clock=lambda: 1000)
    p = Provider(); q.discover(p, 'animes'); published = []
    original = p.exists
    exception = {'pause': BatchPause, 'error': RuntimeError, 'interrupt': KeyboardInterrupt}[failure]
    def exists(*args):
        if len(p.calls) == 1: raise exception()
        return original(*args)
    p.exists = exists
    with statements(q.engine) as captured:
        if failure == 'interrupt':
            with pytest.raises(KeyboardInterrupt): q.run(p, metadata, published.append, discover=False)
        else:
            result = q.run(p, metadata, published.append, discover=False)
            assert result.get('paused' if failure == 'pause' else 'review')
    assert len(checkpoints(captured)) == 1 and not published
    with q.engine.connect() as c:
        saved = json.loads(c.execute(select(jobs.c.source)).scalar_one())['progress']
    assert saved['checked'] == saved['episode_index'] == 1
    p.exists = original
    restarted = VideoAPIQueue(system.security_store, clock=lambda: 1000000)
    with statements(q.engine) as captured:
        assert restarted.run(p, metadata, published.append, discover=False)['imported'] == 1
    assert len(checkpoints(captured)) == 1
    assert [call[-1] for call in p.calls] == [1, 2, 3]
    assert [e['numero'] for e in published[0]['temporadas'][0]['capitulos']] == [1, 3]


def test_publication_failure_reuses_committed_document_without_probing_again(system):
    q = VideoAPIQueue(system.security_store, clock=lambda: 1000)
    p = Provider(); q.discover(p, 'series'); published = []
    def fail(doc): raise RuntimeError('RPC unavailable')
    with statements(q.engine) as captured:
        assert q.run(p, metadata, fail, discover=False)['review']
    assert len(checkpoints(captured)) == 1
    calls = list(p.calls)
    q = VideoAPIQueue(system.security_store, clock=lambda: 10000)
    with statements(q.engine) as captured:
        assert q.run(p, metadata, published.append, discover=False)['imported'] == 1
    assert not checkpoints(captured) and p.calls == calls
    assert len(published[0]['temporadas'][0]['capitulos']) == 2


def test_failed_checkpoint_never_publishes_and_replay_keeps_all_episodes(system):
    q = VideoAPIQueue(system.security_store, clock=lambda: 1000)
    p = Provider(); q.discover(p, 'series'); published = []
    def reject(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE') and 'SET source=' in statement:
            raise RuntimeError('checkpoint unavailable')
    event.listen(q.engine, 'before_cursor_execute', reject)
    try: assert q.run(p, metadata, published.append, discover=False)['review']
    finally: event.remove(q.engine, 'before_cursor_execute', reject)
    assert published == []
    with q.engine.connect() as c:
        assert 'progress' not in json.loads(c.execute(select(jobs.c.source)).scalar_one())
    q = VideoAPIQueue(system.security_store, clock=lambda: 10000)
    assert q.run(p, metadata, published.append, discover=False)['imported'] == 1
    assert [e['numero'] for e in published[0]['temporadas'][0]['capitulos']] == [1, 3]


def test_pause_before_metadata_does_not_write_checkpoint(system):
    q = VideoAPIQueue(system.security_store, clock=lambda: 1000)
    p = Provider(); q.discover(p, 'series')
    def pause(*a): raise BatchPause()
    with statements(q.engine) as captured:
        assert q.run(p, pause, lambda d: pytest.fail('partial publication'), discover=False)['paused']
    assert not checkpoints(captured)
