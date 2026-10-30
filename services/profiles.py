"""Account preferences in the private Supabase PostgreSQL schema.

Local previews use the isolated SecurityStore SQLite database. No remote DDL.
Deleted entries remain as tombstones so an old device cannot restore them.
"""
import time
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, select, update, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from security_store import metadata, accounts

AVATARS = {'tg', 'fox', 'wolf', 'dragon', 'ghost', 'cat', 'alien', 'robot', 'ninja'}
profiles = Table('profiles', metadata,
    Column('account_id', String(36), ForeignKey(accounts.c.id, ondelete='CASCADE'), primary_key=True),
    Column('avatar', String(16), nullable=False),
    Column('updated_at', Float, nullable=False))
saved_items = Table('saved_items', metadata,
    Column('account_id', String(36), ForeignKey(accounts.c.id, ondelete='CASCADE'), primary_key=True),
    Column('content_id', Integer, primary_key=True),
    Column('saved', Integer, nullable=False),
    Column('updated_at', Float, nullable=False))


class Profiles:
    def __init__(self, store):
        self.store = store
        self.insert = sqlite_insert if store.local else pg_insert

    def snapshot(self, account_id):
        with self.store.engine.connect() as c:
            avatar = c.execute(select(profiles.c.avatar).where(profiles.c.account_id == account_id)).scalar_one_or_none()
            ids = list(c.execute(select(saved_items.c.content_id).where(
                saved_items.c.account_id == account_id, saved_items.c.saved == 1
            ).order_by(saved_items.c.updated_at.desc(), saved_items.c.content_id)).scalars())
        return {'avatar': avatar or 'tg', 'saved_ids': ids}

    def is_saved(self, account_id, content_id):
        with self.store.engine.connect() as c:
            return c.execute(select(saved_items.c.saved).where(
                saved_items.c.account_id == account_id,
                saved_items.c.content_id == content_id)).scalar_one_or_none() == 1

    def mutate(self, account_id, *, avatar=None, items=None, bootstrap=False):
        with self.store.engine.begin() as c:
            # An account row serializes concurrent device writes on PostgreSQL
            # and starts the SQLite write lock before reading the current count.
            c.execute(update(accounts).where(accounts.c.id == account_id).values(name=accounts.c.name))
            if avatar is not None:
                stmt = self.insert(profiles).values(account_id=account_id, avatar=avatar, updated_at=time.time())
                stmt = stmt.on_conflict_do_nothing() if bootstrap else stmt.on_conflict_do_update(
                    index_elements=[profiles.c.account_id], set_={'avatar': avatar, 'updated_at': time.time()})
                c.execute(stmt)
            for content_id, saved in (items or []):
                old = c.execute(select(saved_items.c.saved).where(
                    saved_items.c.account_id == account_id, saved_items.c.content_id == content_id)).scalar_one_or_none()
                if bootstrap and old is not None:
                    continue
                if saved and old != 1:
                    count = c.execute(select(func.count()).select_from(saved_items).where(
                        saved_items.c.account_id == account_id, saved_items.c.saved == 1)).scalar_one()
                    if count >= 200:
                        if bootstrap:
                            continue
                        raise ValueError('Puedes guardar hasta 200 títulos. Quita uno antes de añadir otro.')
                stmt = self.insert(saved_items).values(account_id=account_id, content_id=content_id,
                    saved=int(saved), updated_at=time.time())
                stmt = stmt.on_conflict_do_nothing() if bootstrap else stmt.on_conflict_do_update(
                    index_elements=[saved_items.c.account_id, saved_items.c.content_id],
                    set_={'saved': int(saved), 'updated_at': time.time()})
                c.execute(stmt)
