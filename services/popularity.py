"""Weekly popularity from authorized player opens, not measured watch time."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import Table, Column, String, Integer, ForeignKey, Index, select, func, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from security_store import metadata, accounts

opens = Table('playback_opens', metadata,
    Column('account_id', String(36), ForeignKey(accounts.c.id, ondelete='CASCADE'), primary_key=True),
    Column('content_id', Integer, primary_key=True),
    Column('day', Integer, primary_key=True))
Index('playback_opens_day_content', opens.c.day, opens.c.content_id)


def local_day(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(timezone(timedelta(hours=-5))).date().toordinal()


class Popularity:
    def __init__(self, store):
        self.store = store

    def record(self, account_id, content_id, day=None):
        day = local_day() if day is None else day
        insert = sqlite_insert if self.store.local else pg_insert
        with self.store.engine.begin() as c:
            c.execute(delete(opens).where(opens.c.day < day-30))
            result = c.execute(insert(opens).values(account_id=account_id, content_id=content_id, day=day)
                .on_conflict_do_nothing(index_elements=['account_id','content_id','day']))
            return result.rowcount == 1

    def ranking(self, day=None):
        day = local_day() if day is None else day
        count = func.count().label('score')
        with self.store.engine.connect() as c:
            return [dict(row) for row in c.execute(select(opens.c.content_id, count)
                .where(opens.c.day.between(day-6,day)).group_by(opens.c.content_id)
                .order_by(count.desc(), opens.c.content_id.asc()).limit(100)).mappings()]
