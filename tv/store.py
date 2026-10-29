"""Single-use pairing and separately revocable, non-admin television sessions."""
import secrets
import time
from contextlib import contextmanager
from sqlalchemy import Table, Column, String, Float, ForeignKey, select, update, delete
from security_store import metadata, accounts, digest

challenges = Table('tv_pairings', metadata,
    Column('device_hash', String(64), primary_key=True),
    Column('code_hash', String(64), unique=True, nullable=False),
    Column('expires_at', Float, nullable=False),
    Column('account_id', String(36), ForeignKey(accounts.c.id)),
    Column('state', String(16), nullable=False))
devices = Table('tv_devices', metadata,
    Column('token_hash', String(64), primary_key=True),
    Column('account_id', String(36), ForeignKey(accounts.c.id), nullable=False),
    Column('csrf', String(64), nullable=False),
    Column('expires_at', Float, nullable=False),
    Column('created_at', Float, nullable=False))


class PairingStore:
    def __init__(self, security, clock=time.time):
        self.security, self.engine, self.clock = security, security.engine, clock

    @contextmanager
    def transaction(self):
        with self.engine.connect() as c:
            if self.security.local:
                c.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                c.begin()
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise

    def start(self, previous=None):
        token = secrets.token_urlsafe(32)
        code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
        expiry = self.clock() + 600
        with self.transaction() as c:
            c.execute(delete(challenges).where(challenges.c.expires_at <= self.clock()))
            if previous:
                c.execute(delete(challenges).where(challenges.c.device_hash == digest(previous)))
            c.execute(challenges.insert().values(device_hash=digest(token), code_hash=digest(code),
                expires_at=expiry, state='pending'))
        return token, code[:4]+'-'+code[4:], expiry

    def approve(self, code, account_id):
        normalized = str(code).replace('-', '').replace(' ', '').upper()
        if len(normalized) != 8:
            return False
        with self.transaction() as c:
            result = c.execute(update(challenges).where(challenges.c.code_hash == digest(normalized),
                challenges.c.expires_at > self.clock(), challenges.c.state == 'pending')
                .values(account_id=account_id, state='approved'))
            return result.rowcount == 1

    def poll(self, secret):
        if not secret or len(secret) > 128:
            return 'expired', None
        with self.transaction() as c:
            row = c.execute(select(challenges).where(challenges.c.device_hash == digest(secret))
                            .with_for_update()).mappings().first()
            if not row or row['expires_at'] <= self.clock() or row['state'] == 'consumed':
                return 'expired', None
            if row['state'] != 'approved':
                return 'pending', None
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            c.execute(devices.insert().values(token_hash=digest(token), account_id=row['account_id'],
                csrf=csrf, expires_at=self.clock()+604800, created_at=self.clock()))
            c.execute(update(challenges).where(challenges.c.device_hash == row['device_hash'])
                      .values(state='consumed'))
        return 'linked', token

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.engine.connect() as c:
            row = c.execute(select(devices).where(devices.c.token_hash == digest(token),
                devices.c.expires_at > self.clock())).mappings().first()
            return dict(row) if row else None

    def revoke(self, token):
        with self.engine.begin() as c:
            c.execute(delete(devices).where(devices.c.token_hash == digest(token or '')))

    def revoke_account(self, account_id):
        with self.transaction() as c:
            c.execute(delete(devices).where(devices.c.account_id == account_id))
            c.execute(delete(challenges).where(challenges.c.account_id == account_id))
