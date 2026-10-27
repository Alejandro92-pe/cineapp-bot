-- PREPARADO PARA REVISION. NO APLICADO A SUPABASE.

-- No altera usuarios, pagos, contenido, temporadas ni sus politicas.

BEGIN;

CREATE SCHEMA IF NOT EXISTS cine_security;

REVOKE ALL ON SCHEMA cine_security FROM PUBLIC, anon, authenticated;


CREATE TABLE cine_security.accounts (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254), 
	name VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(128), 
	telegram_id BIGINT, 
	created_at FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	UNIQUE (telegram_id)
)

;

ALTER TABLE cine_security.accounts ENABLE ROW LEVEL SECURITY;


CREATE TABLE cine_security.rate_limits (
	key VARCHAR(64) NOT NULL, 
	"window" BIGINT NOT NULL, 
	hits INTEGER NOT NULL, 
	PRIMARY KEY (key, "window")
)

;

ALTER TABLE cine_security.rate_limits ENABLE ROW LEVEL SECURITY;


CREATE TABLE cine_security.webhook_events (
	key VARCHAR(64) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	created_at FLOAT NOT NULL, 
	PRIMARY KEY (key)
)

;

ALTER TABLE cine_security.webhook_events ENABLE ROW LEVEL SECURITY;


CREATE TABLE cine_security.sessions (
	token_hash VARCHAR(64) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	csrf VARCHAR(64) NOT NULL, 
	expires_at FLOAT NOT NULL, 
	admin INTEGER NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(account_id) REFERENCES cine_security.accounts (id)
)

;

ALTER TABLE cine_security.sessions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON ALL TABLES IN SCHEMA cine_security FROM PUBLIC, anon, authenticated;

COMMIT;
