import secrets
import time
import uuid
from contextlib import contextmanager
from sqlalchemy import select, update, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from security_store import accounts, digest
from billing.schema import orders, access, receipts, assets, review_events
from billing.config import METHODS


class PaymentError(ValueError):
    pass


class BillingStore:
    def __init__(self, security_store):
        self.engine, self.local = security_store.engine, security_store.local

    @contextmanager
    def transaction(self, account_id=None):
        with self.engine.connect() as c:
            if self.local:
                c.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                c.begin()
            try:
                if account_id:
                    # All renewals of the same account serialize across workers.
                    c.execute(select(accounts.c.id).where(accounts.c.id == account_id).with_for_update()).scalar_one()
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise

    def get(self, order_id):
        with self.engine.connect() as c:
            row = c.execute(select(orders).where(orders.c.id == order_id)).mappings().first()
            return dict(row) if row else None

    def by_code(self, code):
        with self.engine.connect() as c:
            row = c.execute(select(orders).where(orders.c.code == code)).mappings().first()
            return dict(row) if row else None

    def create(self, account_id, method):
        if not isinstance(method, str) or method not in METHODS:
            raise PaymentError("Selecciona un método de pago disponible.")
        with self.transaction(account_id) as c:
            row = c.execute(select(orders).where(orders.c.account_id == account_id, orders.c.method == method,
                orders.c.status.in_(["pending_provider", "draft", "pending_review"])).order_by(orders.c.created_at.desc())).mappings().first()
            if row:
                return dict(row)
            item = dict(id=str(uuid.uuid4()), code="QH-"+secrets.token_hex(10).upper(), account_id=account_id,
                method=method, amount_minor=METHODS[method]["amount_minor"], currency=METHODS[method]["currency"], days=30,
                status="pending_provider" if method == "bmc" else "draft", created_at=time.time(), updated_at=time.time())
            c.execute(orders.insert().values(**item))
            return self.get_in(c, item["id"])

    @staticmethod
    def get_in(c, order_id):
        return dict(c.execute(select(orders).where(orders.c.id == order_id)).mappings().one())

    def report(self, order_id, account_id, reference, payer, paid_date):
        with self.transaction(account_id) as c:
            row = self.get_in(c, order_id)
            if row["account_id"] != account_id or row["method"] == "bmc":
                raise PaymentError("No puedes registrar este pago.")
            if row["status"] == "pending_review":
                if row["reference"] == reference:
                    return row
                raise PaymentError("El pago ya está en revisión. Espera la respuesta del administrador.")
            if row["status"] != "draft":
                raise PaymentError("Esta solicitud ya fue procesada.")
            c.execute(update(orders).where(orders.c.id == order_id).values(status="pending_review", reference=reference,
                payer=payer, paid_date=paid_date, updated_at=time.time()))
            return self.get_in(c, order_id)

    def decide(self, order_id, approved, reviewer=None, baseline=0, provider_reference=None, reason=""):
        before = self.get(order_id)
        if not before:
            raise PaymentError("Solicitud no encontrada.")
        with self.transaction(before["account_id"]) as c:
            row = self.get_in(c, order_id)
            expected = "pending_provider" if provider_reference else "pending_review"
            if row["status"] == "approved" and approved:
                if provider_reference and row["reference"] != provider_reference:
                    raise PaymentError("La solicitud ya corresponde a otro pago.")
                return {**row, "duplicate": True}
            if row["status"] != expected or (row["method"] == "bmc") != bool(provider_reference):
                raise PaymentError("Esta solicitud no admite esa operación.")
            if not approved:
                c.execute(update(orders).where(orders.c.id == order_id).values(status="rejected", reason=reason,
                    reviewer=reviewer, updated_at=time.time()))
                return self.get_in(c, order_id)
            reference = provider_reference or row["reference"]
            key = digest(row["method"]+":"+reference)
            ins = sqlite_insert if self.local else pg_insert
            claim = ins(receipts).values(key=key, order_id=order_id, created_at=time.time()).on_conflict_do_nothing().returning(receipts.c.key)
            if c.execute(claim).scalar_one_or_none() is None:
                raise PaymentError("Este número de operación ya activó otra solicitud. Revisa el ingreso.")
            prior = c.execute(select(access.c.expires_at).where(access.c.account_id == row["account_id"])).scalar_one_or_none() or 0
            expires = max(time.time(), prior, baseline or 0) + row["days"]*86400
            stmt = ins(access).values(account_id=row["account_id"], expires_at=expires)
            c.execute(stmt.on_conflict_do_update(index_elements=[access.c.account_id], set_={"expires_at": expires}))
            c.execute(update(orders).where(orders.c.id == order_id).values(status="approved", reference=reference,
                reviewer=reviewer, expires_at=expires, updated_at=time.time(), reason=None))
            return self.get_in(c, order_id)

    def expiry(self, account_id):
        with self.engine.connect() as c:
            return c.execute(select(access.c.expires_at).where(access.c.account_id == account_id)).scalar_one_or_none() or 0

    def history(self, account_id=None):
        query = select(orders, accounts.c.name, accounts.c.email).join(accounts, orders.c.account_id == accounts.c.id)
        if account_id:
            query = query.where(orders.c.account_id == account_id)
        recent = select(orders.c.id).order_by(orders.c.created_at.desc()).limit(100)
        if account_id:
            recent = recent.where(orders.c.account_id == account_id)
        # Never hide a pending request behind the recent-history limit.
        query = query.where(or_(orders.c.id.in_(recent), orders.c.status.in_(["pending_provider", "pending_review", "draft"])))
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(query.order_by(orders.c.created_at.desc())).mappings()]

    def review(self, payment_id, reason):
        ins = sqlite_insert if self.local else pg_insert
        with self.engine.begin() as c:
            c.execute(ins(review_events).values(key=digest("bmc:"+str(payment_id)+":"+reason), payment_id=str(payment_id)[:80],
                reason=reason, created_at=time.time()).on_conflict_do_nothing())

    def reviews(self):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(review_events).order_by(review_events.c.created_at.desc()).limit(100)).mappings()]

    def qr(self, method):
        with self.engine.connect() as c:
            row = c.execute(select(assets).where(assets.c.method == method)).mappings().first()
            return dict(row) if row else None

    def save_qr(self, method, data, mime, recipient):
        ins = sqlite_insert if self.local else pg_insert
        values = dict(method=method,data=data,mime=mime,recipient=recipient,updated_at=time.time())
        with self.engine.begin() as c:
            c.execute(ins(assets).values(**values).on_conflict_do_update(index_elements=[assets.c.method],set_=values))
