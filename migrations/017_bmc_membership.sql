-- 017 · Membresía IMAX de Buy Me a Coffee (US$2/mes) y registro detallado de avisos BMC.
-- Apply manually in the Supabase SQL editor, AFTER 003_monthly_payments.sql. Never automatic.
-- Safe to run twice. Keeps every existing order: old prices (US$1.50, S/5.50, 1.50 USDT) stay valid.
BEGIN;

ALTER TABLE cine_security.payment_orders DROP CONSTRAINT IF EXISTS monthly_prices;
ALTER TABLE cine_security.payment_orders ADD CONSTRAINT monthly_prices CHECK (
	(method = 'bmc' AND amount_minor IN (150, 200) AND currency = 'USD') OR
	(method = 'yape_plin' AND amount_minor IN (550, 750) AND currency = 'PEN') OR
	(method = 'binance' AND amount_minor IN (150, 200) AND currency = 'USDT'));

CREATE TABLE IF NOT EXISTS cine_security.bmc_memberships (
	id VARCHAR(40) NOT NULL,
	account_id VARCHAR(36),
	email VARCHAR(254),
	name VARCHAR(120),
	level_id VARCHAR(20),
	level_name VARCHAR(80),
	status VARCHAR(20) NOT NULL,
	amount VARCHAR(12),
	currency VARCHAR(5),
	period_end FLOAT,
	canceled INTEGER NOT NULL DEFAULT 0,
	link_method VARCHAR(20),
	created_at FLOAT NOT NULL,
	updated_at FLOAT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(account_id) REFERENCES cine_security.accounts (id)
);
CREATE INDEX IF NOT EXISTS ix_cine_security_bmc_memberships_account_id ON cine_security.bmc_memberships (account_id);
ALTER TABLE cine_security.bmc_memberships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.bmc_memberships FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS cine_security.bmc_events (
	id VARCHAR(64) NOT NULL,
	type VARCHAR(40) NOT NULL,
	object_id VARCHAR(40),
	email VARCHAR(254),
	name VARCHAR(120),
	amount VARCHAR(12),
	currency VARCHAR(5),
	outcome VARCHAR(20) NOT NULL,
	detail VARCHAR(400),
	account_id VARCHAR(36),
	received_at FLOAT NOT NULL,
	payload TEXT,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS bmc_events_received ON cine_security.bmc_events (received_at DESC);
CREATE INDEX IF NOT EXISTS bmc_events_account ON cine_security.bmc_events (account_id);
ALTER TABLE cine_security.bmc_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.bmc_events FROM PUBLIC, anon, authenticated;

COMMIT;
