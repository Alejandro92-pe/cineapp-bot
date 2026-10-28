"""One provider per cron request; outages never strand the other queue."""
from services.catalog_jobs import run_production_batch
from services.videoapi_jobs import VideoAPIQueue, run_videoapi_batch

INTERVAL_SECONDS = 300
PROVIDER_CYCLE = ('videoapi', 'videoapi', 'videoapi', 'videoapi', 'vimeus')

def run_batch(queue, store, database, *, videoapi_enabled=False, vimeus_key='', tmdb_key=''):
    if not videoapi_enabled:
        return run_production_batch(queue, database, vimeus_key, tmdb_key)
    # Move the cursor before I/O. A provider timeout cannot monopolize later calls.
    with queue.lock() as acquired:
        if not acquired: return {'busy': True}
        if queue.get_setting('scheduler_after') > queue.clock(): return {'waiting': True}
        turn = int(queue.get_setting('provider_turn'))
        queue.set_setting('provider_turn', turn+1)
        now = queue.clock()
        # External cron arrivals jitter by a few seconds. Reserve this wall-clock
        # slot, not 300 seconds after arrival (which would skip the next early tick).
        # The extra 60-second floor prevents bursts across adjacent boundaries.
        boundary = (int(now)//INTERVAL_SECONDS+1)*INTERVAL_SECONDS
        queue.set_setting('scheduler_after', max(now+60, boundary))
    if PROVIDER_CYCLE[turn % len(PROVIDER_CYCLE)] == 'videoapi' or not vimeus_key:
        return {'provider': 'videoapi', **run_videoapi_batch(VideoAPIQueue(store), database, tmdb_key)}
    return {'provider': 'vimeus', **run_production_batch(queue, database, vimeus_key, tmdb_key)}
