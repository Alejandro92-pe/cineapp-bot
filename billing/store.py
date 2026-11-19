import json
import secrets
import time
import uuid
from contextlib import contextmanager
from sqlalchemy import select, update, or_, func, String as SAString
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from security_store import accounts, digest
from billing.schema import orders, access, receipts, assets, review_events, memberships, bmc_events
from billing.config import METHODS, MEMBERSHIP_GRACE


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

    def create(self, account_id, method, payer=None):
        """payer, for BMC, is the email the person will use in Buy Me a Coffee."""
        if not isinstance(method, str) or method not in METHODS:
            raise PaymentError("Selecciona un método de pago disponible.")
        with self.transaction(account_id) as c:
            # Reuse an open request only at today's price; old-price drafts stay in the history.
            row = c.execute(select(orders).where(orders.c.account_id == account_id, orders.c.method == method,
                orders.c.amount_minor == METHODS[method]["amount_minor"],
                orders.c.status.in_(["pending_provider", "draft", "pending_review"])).order_by(orders.c.created_at.desc())).mappings().first()
            if row:
                if payer and row["payer"] != payer and row["status"] == "pending_provider":
                    c.execute(update(orders).where(orders.c.id == row["id"]).values(payer=payer, updated_at=time.time()))
                return self.get_in(c, row["id"])
            item = dict(id=str(uuid.uuid4()), code="QH-"+secrets.token_hex(10).upper(), account_id=account_id,
                method=method, amount_minor=METHODS[method]["amount_minor"], currency=METHODS[method]["currency"], days=30,
                status="pending_provider" if method == "bmc" else "draft", created_at=time.time(), updated_at=time.time(),
                payer=payer if method == "bmc" else None)
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

    # ------------------------------------------------------------ BMC events and memberships

    def log_event(self, event_id, kind, outcome, detail="", object_id=None, email=None, name=None,
                  amount=None, currency=None, account_id=None, payload=None):
        """Upsert by event id: a BMC retry replaces the outcome of the previous attempt."""
        values = dict(id=str(event_id)[:64], type=str(kind or "?")[:40],
                      object_id=str(object_id)[:40] if object_id is not None else None,
                      email=str(email)[:254] if email else None, name=str(name)[:120] if name else None,
                      amount=None if amount is None else str(amount)[:12], currency=str(currency)[:5] if currency else None,
                      outcome=outcome[:20], detail=(detail or "")[:400], account_id=account_id, received_at=time.time(),
                      payload=None if payload is None else json.dumps(payload, ensure_ascii=False)[:20000])
        ins = sqlite_insert if self.local else pg_insert
        with self.engine.begin() as c:
            c.execute(ins(bmc_events).values(**values).on_conflict_do_update(index_elements=[bmc_events.c.id],
                set_={k: v for k, v in values.items() if k != "id"}))

    def events(self, limit=200):
        cols = [col for col in bmc_events.c if col.name != "payload"]
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(*cols).order_by(bmc_events.c.received_at.desc()).limit(limit)).mappings()]

    def event_payload(self, event_id):
        with self.engine.connect() as c:
            raw = c.execute(select(bmc_events.c.payload).where(bmc_events.c.id == str(event_id))).scalar_one_or_none()
        return json.loads(raw) if raw else None

    def save_membership(self, membership_id, **fields):
        """Insert or refresh a membership; never drops an existing account link."""
        now = time.time()
        ins = sqlite_insert if self.local else pg_insert
        values = dict(id=str(membership_id), created_at=now, updated_at=now, **fields)
        update_set = {k: v for k, v in values.items() if k not in ("id", "created_at", "account_id", "link_method")}
        with self.engine.begin() as c:
            c.execute(ins(memberships).values(**values).on_conflict_do_update(index_elements=[memberships.c.id], set_=update_set))
            return dict(c.execute(select(memberships).where(memberships.c.id == str(membership_id))).mappings().one())

    def membership(self, membership_id):
        with self.engine.connect() as c:
            row = c.execute(select(memberships).where(memberships.c.id == str(membership_id))).mappings().first()
            return dict(row) if row else None

    def memberships(self):
        query = (select(memberships, accounts.c.name.label("account_name"), accounts.c.email.label("account_email"))
                 .outerjoin(accounts, memberships.c.account_id == accounts.c.id)
                 .order_by(memberships.c.updated_at.desc()).limit(300))
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(query).mappings()]

    def match_account(self, email):
        """One account whose email, or whose recent BMC request, uses this email. Ambiguity goes to the admin."""
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            return None, "BMC no envió el email de quien pagó."
        with self.engine.connect() as c:
            by_account = set(c.execute(select(accounts.c.id).where(func.lower(accounts.c.email) == email)).scalars())
            by_request = set(c.execute(select(orders.c.account_id).where(orders.c.method == "bmc",
                func.lower(orders.c.payer) == email, orders.c.created_at > time.time() - 45 * 86400)).scalars())
        found = by_account | by_request
        if len(found) == 1:
            return next(iter(found)), ("email de la cuenta" if by_account else "email indicado al pagar")
        if found:
            return None, f"Hay {len(found)} cuentas con el email {email}: elige la correcta."
        return None, f"Ninguna cuenta de la web usa el email {email}."

    def grant_membership(self, membership_id, account_id, period_end, baseline=0, reviewer=None, link_method=None):
        """Access until the paid period ends (+grace). Idempotent: repeated events never add extra time."""
        now = time.time()
        until = float(period_end) + MEMBERSHIP_GRACE
        reference = f"M{membership_id}-{int(period_end)}"
        with self.transaction(account_id) as c:
            values = {"account_id": account_id, "updated_at": now}
            if link_method:
                values["link_method"] = link_method
            c.execute(update(memberships).where(memberships.c.id == str(membership_id)).values(**values))
            prior = c.execute(select(access.c.expires_at).where(access.c.account_id == account_id)).scalar_one_or_none() or 0
            expires = max(prior, baseline or 0, until)
            ins = sqlite_insert if self.local else pg_insert
            c.execute(ins(access).values(account_id=account_id, expires_at=expires)
                      .on_conflict_do_update(index_elements=[access.c.account_id], set_={"expires_at": expires}))
            # Show the payment in the person's history: close their open BMC request, or record the renewal.
            seen = c.execute(select(orders.c.id).where(orders.c.reference == reference)).first()
            if not seen:
                pending = c.execute(select(orders.c.id).where(orders.c.account_id == account_id, orders.c.method == "bmc",
                    orders.c.status == "pending_provider").order_by(orders.c.created_at.desc())).scalars().first()
                if pending:
                    c.execute(update(orders).where(orders.c.id == pending).values(status="approved", reference=reference,
                        amount_minor=METHODS["bmc"]["amount_minor"], expires_at=expires, reviewer=reviewer,
                        updated_at=now, reason="Membresía IMAX"))
                else:
                    c.execute(orders.insert().values(id=str(uuid.uuid4()), code="QH-"+secrets.token_hex(10).upper(),
                        account_id=account_id, method="bmc", amount_minor=METHODS["bmc"]["amount_minor"], currency="USD",
                        days=30, status="approved", created_at=now, updated_at=now, reference=reference,
                        expires_at=expires, reviewer=reviewer, reason="Membresía IMAX"))
            return expires

    # ------------------------------------------------------------ admin overview

    def accounts_overview(self, query=None, limit=300):
        from services.popularity import opens
        order_stats = (select(orders.c.account_id, func.count().label("orders"),
                              func.max(orders.c.created_at).label("last_order_at"))
                       .group_by(orders.c.account_id).subquery())
        watched = (select(opens.c.account_id, func.count(func.distinct(opens.c.content_id)).label("titles"),
                          func.max(opens.c.day).label("last_day")).group_by(opens.c.account_id).subquery())
        stmt = (select(accounts.c.id, accounts.c.name, accounts.c.email, accounts.c.telegram_id, accounts.c.created_at,
                       access.c.expires_at, order_stats.c.orders, order_stats.c.last_order_at,
                       watched.c.titles, watched.c.last_day)
                .outerjoin(access, access.c.account_id == accounts.c.id)
                .outerjoin(order_stats, order_stats.c.account_id == accounts.c.id)
                .outerjoin(watched, watched.c.account_id == accounts.c.id))
        if query:
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(accounts.c.name).like(like), func.lower(accounts.c.email).like(like),
                                  func.cast(accounts.c.telegram_id, SAString).like(like)))
        with self.engine.connect() as c:
            rows = [dict(r) for r in c.execute(stmt.order_by(accounts.c.created_at.desc()).limit(limit)).mappings()]
            total = c.execute(select(func.count()).select_from(accounts)).scalar_one()
            last_status = {}
            ids = [r["id"] for r in rows]
            if ids:
                for r in c.execute(select(orders.c.account_id, orders.c.status, orders.c.method)
                                   .where(orders.c.account_id.in_(ids)).order_by(orders.c.created_at)).mappings():
                    last_status[r["account_id"]] = {"status": r["status"], "method": r["method"]}
        for r in rows:
            r["last_order"] = last_status.get(r["id"])
        return rows, total

    def account_detail(self, account_id):
        from services.popularity import opens
        with self.engine.connect() as c:
            account = c.execute(select(accounts.c.id, accounts.c.name, accounts.c.email, accounts.c.telegram_id,
                                       accounts.c.created_at).where(accounts.c.id == account_id)).mappings().first()
            if not account:
                return None
            expires = c.execute(select(access.c.expires_at).where(access.c.account_id == account_id)).scalar_one_or_none()
            history = [dict(r) for r in c.execute(select(orders).where(orders.c.account_id == account_id)
                                                  .order_by(orders.c.created_at.desc()).limit(50)).mappings()]
            linked = [dict(r) for r in c.execute(select(memberships).where(memberships.c.account_id == account_id)).mappings()]
            cols = [col for col in bmc_events.c if col.name != "payload"]
            events = [dict(r) for r in c.execute(select(*cols).where(bmc_events.c.account_id == account_id)
                                                 .order_by(bmc_events.c.received_at.desc()).limit(50)).mappings()]
            plays = [dict(r) for r in c.execute(select(opens.c.content_id, opens.c.day).where(opens.c.account_id == account_id)
                                                .order_by(opens.c.day.desc()).limit(30)).mappings()]
        return {"account": dict(account), "expires_at": expires, "orders": history, "memberships": linked,
                "events": events, "plays": plays}
