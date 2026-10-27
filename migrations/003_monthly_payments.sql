-- Local review only. Apply AFTER 001_security.sql, never automatically.
BEGIN;

CREATE TABLE IF NOT EXISTS cine_security.payment_qr_assets (
	method VARCHAR(20) NOT NULL, 
	data BYTEA NOT NULL, 
	mime VARCHAR(30) NOT NULL, 
	recipient VARCHAR(100) NOT NULL, 
	updated_at FLOAT NOT NULL, 
	PRIMARY KEY (method)
)

;
ALTER TABLE cine_security.payment_qr_assets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.payment_qr_assets FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS cine_security.payment_review_events (
	key VARCHAR(64) NOT NULL, 
	payment_id VARCHAR(80) NOT NULL, 
	reason VARCHAR(300) NOT NULL, 
	created_at FLOAT NOT NULL, 
	PRIMARY KEY (key)
)

;
ALTER TABLE cine_security.payment_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.payment_review_events FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS cine_security.paid_access (
	account_id VARCHAR(36) NOT NULL, 
	expires_at FLOAT NOT NULL, 
	PRIMARY KEY (account_id), 
	FOREIGN KEY(account_id) REFERENCES cine_security.accounts (id)
)

;
ALTER TABLE cine_security.paid_access ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.paid_access FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS cine_security.payment_orders (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	method VARCHAR(20) NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR(5) NOT NULL, 
	days INTEGER NOT NULL, 
	status VARCHAR(25) NOT NULL, 
	created_at FLOAT NOT NULL, 
	updated_at FLOAT NOT NULL, 
	reference VARCHAR(100), 
	payer VARCHAR(80), 
	paid_date VARCHAR(10), 
	reason VARCHAR(300), 
	reviewer VARCHAR(36), 
	expires_at FLOAT, 
	PRIMARY KEY (id), 
	CONSTRAINT monthly_days CHECK (days = 30), 
	CONSTRAINT monthly_prices CHECK ((method = 'bmc' AND amount_minor = 150 AND currency = 'USD') OR (method = 'yape_plin' AND amount_minor = 550 AND currency = 'PEN') OR (method = 'binance' AND amount_minor = 150 AND currency = 'USDT')), 
	CONSTRAINT payment_status CHECK (status IN ('draft','pending_provider','pending_review','approved','rejected')), 
	UNIQUE (code), 
	FOREIGN KEY(account_id) REFERENCES cine_security.accounts (id)
)

;
CREATE INDEX IF NOT EXISTS ix_cine_security_payment_orders_account_id ON cine_security.payment_orders (account_id);
ALTER TABLE cine_security.payment_orders ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.payment_orders FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS cine_security.payment_receipts (
	key VARCHAR(64) NOT NULL, 
	order_id VARCHAR(36) NOT NULL, 
	created_at FLOAT NOT NULL, 
	PRIMARY KEY (key), 
	UNIQUE (order_id), 
	FOREIGN KEY(order_id) REFERENCES cine_security.payment_orders (id)
)

;
ALTER TABLE cine_security.payment_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.payment_receipts FROM PUBLIC, anon, authenticated;
COMMIT;
