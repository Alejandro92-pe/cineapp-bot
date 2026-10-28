"""Three shared hero titles per three Lima calendar days; no external API calls."""
import hashlib
import json
import time
from sqlalchemy import select
from services.catalog_jobs import cache

PERIOD = 3 * 86400
LIMA_OFFSET = 5 * 3600


def choose_ids(candidates, period, previous=()):
    """Stable shuffle, preferring titles absent from the previous selection."""
    ids = set(candidates)
    prior = set(previous)
    return sorted(ids, key=lambda value: (
        value in prior,
        hashlib.sha256(f'quehay-hero:{period}:{value}'.encode()).digest()
    ))[:3]


class HeroRotation:
    def __init__(self, queue, catalog, clock=time.time):
        self.queue, self.catalog, self.clock = queue, catalog, clock

    def movies(self, fields):
        return self.catalog.table('contenido').select(fields).eq('tipo', 'pelicula').eq('disponible', True)

    def titles(self):
        period = int((self.clock() - LIMA_OFFSET) // PERIOD)
        key = f'hero:{period}'
        with self.queue.engine.connect() as c:
            snapshots = dict(c.execute(select(cache.c.key, cache.c.payload).where(
                cache.c.key.in_([key, f'hero:{period-1}']))).all())
        if key not in snapshots:
            candidates = []
            offset = 0
            while True:
                rows = self.movies('id,imagen_url,backdrop_url').order('id').range(offset, offset+499).execute().data
                candidates.extend(row['id'] for row in rows if row.get('backdrop_url') or row.get('imagen_url'))
                if len(rows) < 500:
                    break
                offset += len(rows)
            ids = choose_ids(candidates, period, json.loads(snapshots.get(f'hero:{period-1}', '[]')))
            # Do not freeze an empty catalogue for three days.
            if not ids:
                return []
            with self.queue.engine.begin() as c:
                # Concurrent first visitors share the winning snapshot. Keep it
                # through the next period so imports/restarts cannot reshuffle it.
                c.execute(self.queue.insert(cache).values(key=key, payload=json.dumps(ids),
                    expires=(period+2)*PERIOD+LIMA_OFFSET).on_conflict_do_nothing(index_elements=['key']))
                snapshots[key] = c.execute(select(cache.c.payload).where(cache.c.key == key)).scalar_one()
        ids = json.loads(snapshots[key])
        # Recheck visibility on every request, even for a stored selection.
        rows = self.movies('*').in_('id', ids).execute().data
        by_id = {row['id']: row for row in rows}
        return [by_id[value] for value in ids if value in by_id]
