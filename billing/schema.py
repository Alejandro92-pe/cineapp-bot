from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, LargeBinary, CheckConstraint, Text
from security_store import metadata, accounts

# Historic rows keep their price: US$1.50 / S/5.50 / 1.50 USDT until November 2026,
# then US$2 / S/7.50 / 2 USDT. Both sets stay valid (migration 017).
PRICE_RULE = ("(method = 'bmc' AND amount_minor IN (150, 200) AND currency = 'USD') OR "
              "(method = 'yape_plin' AND amount_minor IN (550, 750) AND currency = 'PEN') OR "
              "(method = 'binance' AND amount_minor IN (150, 200) AND currency = 'USDT')")

orders = Table("payment_orders", metadata,
    Column("id", String(36), primary_key=True),
    Column("code", String(40), nullable=False, unique=True),
    Column("account_id", String(36), ForeignKey(accounts.c.id), nullable=False, index=True),
    Column("method", String(20), nullable=False),
    Column("amount_minor", Integer, nullable=False),
    Column("currency", String(5), nullable=False),
    Column("days", Integer, nullable=False),
    Column("status", String(25), nullable=False),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    Column("reference", String(100)),
    Column("payer", String(80)),
    Column("paid_date", String(10)),
    Column("reason", String(300)),
    Column("reviewer", String(36)),
    Column("expires_at", Float),
    CheckConstraint("days = 30", name="monthly_days"),
    CheckConstraint(PRICE_RULE, name="monthly_prices"),
    CheckConstraint("status IN ('draft','pending_provider','pending_review','approved','rejected')", name="payment_status"))
access = Table("paid_access", metadata,
    Column("account_id", String(36), ForeignKey(accounts.c.id), primary_key=True),
    Column("expires_at", Float, nullable=False))
receipts = Table("payment_receipts", metadata,
    Column("key", String(64), primary_key=True),
    Column("order_id", String(36), ForeignKey(orders.c.id), nullable=False, unique=True),
    Column("created_at", Float, nullable=False))
assets = Table("payment_qr_assets", metadata,
    Column("method", String(20), primary_key=True),
    Column("data", LargeBinary, nullable=False),
    Column("mime", String(30), nullable=False),
    Column("recipient", String(100), nullable=False),
    Column("updated_at", Float, nullable=False))
review_events = Table("payment_review_events", metadata,
    Column("key", String(64), primary_key=True),
    Column("payment_id", String(80), nullable=False),
    Column("reason", String(300), nullable=False),
    Column("created_at", Float, nullable=False))

# One row per Buy Me a Coffee membership. The link to an account survives renewals.
memberships = Table("bmc_memberships", metadata,
    Column("id", String(40), primary_key=True),
    Column("account_id", String(36), ForeignKey(accounts.c.id), index=True),
    Column("email", String(254)),
    Column("name", String(120)),
    Column("level_id", String(20)),
    Column("level_name", String(80)),
    Column("status", String(20), nullable=False),
    Column("amount", String(12)),
    Column("currency", String(5)),
    Column("period_end", Float),
    Column("canceled", Integer, nullable=False, default=0),
    Column("link_method", String(20)),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False))

# Every signed BMC delivery, with what the web did and why. Retries share the event id.
bmc_events = Table("bmc_events", metadata,
    Column("id", String(64), primary_key=True),
    Column("type", String(40), nullable=False),
    Column("object_id", String(40)),
    Column("email", String(254)),
    Column("name", String(120)),
    Column("amount", String(12)),
    Column("currency", String(5)),
    Column("outcome", String(20), nullable=False),
    Column("detail", String(400)),
    Column("account_id", String(36)),
    Column("received_at", Float, nullable=False),
    Column("payload", Text))
