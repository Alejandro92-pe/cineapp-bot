"""Private accounts/sessions. SQLite only in local mode; PostgreSQL in production.

No production DDL is executed here. See migrations/001_security.sql.
"""
import hashlib
import secrets
import time
import uuid

from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Float,
                        Integer, ForeignKey, create_engine, select, delete, update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

metadata = MetaData(schema="cine_security")
accounts = Table("accounts", metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(254), unique=True),
    Column("name", String(80), nullable=False),
    Column("password_hash", String(128)),
    Column("telegram_id", BigInteger, unique=True),
    Column("created_at", Float, nullable=False))
sessions = Table("sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("account_id", String(36), ForeignKey(accounts.c.id), nullable=False),
    Column("csrf", String(64), nullable=False),
    Column("expires_at", Float, nullable=False),
    Column("admin", Integer, nullable=False, default=0))
admin_leases = Table('admin_leases', metadata,
    Column('token_hash', String(64), ForeignKey(sessions.c.token_hash, ondelete='CASCADE'), primary_key=True),
    Column('expires_at', Float, nullable=False))
limits = Table("rate_limits", metadata,
    Column("key", String(64), primary_key=True),
    Column("window", BigInteger, primary_key=True),
    Column("hits", Integer, nullable=False))
events = Table("webhook_events", metadata,
    Column("key", String(64), primary_key=True),
    Column("state", String(20), nullable=False),
    Column("created_at", Float, nullable=False))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class SecurityStore:
    def __init__(self, url, local=False):
        if not local and not url.startswith("postgresql+psycopg://"):
            raise RuntimeError("SECURITY_DATABASE_URL debe usar PostgreSQL en producción.")
        if not local and make_url(url).query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
            raise RuntimeError("La conexión de seguridad requiere TLS en producción.")
        if local and not url.startswith("sqlite:///"):
            raise RuntimeError("El modo local solo permite una base SQLite aislada.")
        options = {"pool_pre_ping": True, "hide_parameters": True}
        if local:
            options.update(connect_args={"check_same_thread": False, "timeout": 30},
                           execution_options={"schema_translate_map": {"cine_security": None}})
        self.engine = create_engine(url, **options)
        self.local = local
        from billing import schema  # Register private payment tables before local DDL.
        from services import popularity  # Private ranking table; production needs migration 006.
        from services import profiles  # Private account preferences; migration 010 in production.
        from services import catalog_jobs  # Durable production queue; migration 014.
        from services import videoapi_jobs  # Independent queue; migration 015.
        if local:
            metadata.create_all(self.engine)

    def account(self, **criteria):
        with self.engine.connect() as c:
            row = c.execute(select(accounts).filter_by(**criteria)).mappings().first()
            return dict(row) if row else None

    def create_account(self, name, email=None, password_hash=None, telegram_id=None):
        item = dict(id=str(uuid.uuid4()), name=name, email=email,
                    password_hash=password_hash, telegram_id=telegram_id, created_at=time.time())
        with self.engine.begin() as c:
            c.execute(accounts.insert().values(**item))
        return item

    def link_telegram(self, account_id, telegram_id):
        with self.engine.begin() as c:
            result = c.execute(update(accounts).where(accounts.c.id == account_id,
                accounts.c.telegram_id.is_(None)).values(telegram_id=telegram_id))
            return result.rowcount == 1

    def new_session(self, account_id, ttl=604800, admin=False, old_token=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.engine.begin() as c:
            c.execute(delete(sessions).where(sessions.c.expires_at <= time.time()))
            if old_token:
                c.execute(delete(sessions).where(sessions.c.token_hash == digest(old_token)))
            c.execute(sessions.insert().values(token_hash=digest(token), account_id=account_id,
                csrf=csrf, expires_at=time.time()+ttl, admin=0))
            if admin:
                c.execute(admin_leases.insert().values(token_hash=digest(token), expires_at=time.time()+3600))
        return token, csrf

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.engine.connect() as c:
            row = c.execute(select(sessions, admin_leases.c.expires_at.label('admin_until'),
                *[col.label('identity_'+col.name) for col in accounts.c])
                .join(accounts, accounts.c.id == sessions.c.account_id)
                .outerjoin(admin_leases, admin_leases.c.token_hash == sessions.c.token_hash)
                .where(sessions.c.token_hash == digest(token),
                sessions.c.expires_at > time.time())).mappings().first()
            if not row:
                return None
            result = {col.name: row[col.name] for col in sessions.c}
            until = row['admin_until']
            # Elevation lives only in its short lease. The legacy flag stays 0,
            # so rolling back older code cannot grant seven-day admin access.
            result['admin'] = int(until is not None and until > time.time())
            result["account"] = {col.name: row['identity_'+col.name] for col in accounts.c}
            return result

    def revoke(self, token):
        with self.engine.begin() as c:
            c.execute(delete(sessions).where(sessions.c.token_hash == digest(token or "")))

    def change_password(self, account_id, password_hash):
        with self.engine.begin() as c:
            c.execute(update(accounts).where(accounts.c.id == account_id).values(password_hash=password_hash))
            c.execute(delete(sessions).where(sessions.c.account_id == account_id))

    def allow_attempt(self, key, maximum=10, seconds=900):
        window = int(time.time()) // seconds
        ins = sqlite_insert if self.local else pg_insert
        stmt = ins(limits).values(key=digest(key), window=window, hits=1)
        stmt = stmt.on_conflict_do_update(index_elements=[limits.c.key, limits.c.window],
                                         set_={"hits": limits.c.hits+1}).returning(limits.c.hits)
        with self.engine.begin() as c:
            c.execute(delete(limits).where(limits.c.window < window-2))
            hits = c.execute(stmt).scalar_one()
        return hits <= maximum

    def claim_event(self, key):
        try:
            with self.engine.begin() as c:
                c.execute(events.insert().values(key=digest(key), state="processing", created_at=time.time()))
            return "new"
        except IntegrityError:
            with self.engine.connect() as c:
                return c.execute(select(events.c.state).where(events.c.key == digest(key))).scalar_one()

    def finish_event(self, key, state="done"):
        with self.engine.begin() as c:
            c.execute(update(events).where(events.c.key == digest(key)).values(state=state))
