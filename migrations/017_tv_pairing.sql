-- PREPARED ONLY. Apply to Supabase only after deployment approval.
-- Additive private tables; accounts, payments, catalog and downloads are unchanged.
BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.tv_pairings (
 device_hash VARCHAR(64) PRIMARY KEY,
 code_hash VARCHAR(64) UNIQUE NOT NULL,
 expires_at DOUBLE PRECISION NOT NULL,
 account_id VARCHAR(36) REFERENCES cine_security.accounts(id) ON DELETE CASCADE,
 identity_stamp VARCHAR(64),
 state VARCHAR(16) NOT NULL CHECK(state IN ('pending','approved','consumed'))
);
CREATE TABLE IF NOT EXISTS cine_security.tv_devices (
 token_hash VARCHAR(64) PRIMARY KEY,
 account_id VARCHAR(36) NOT NULL REFERENCES cine_security.accounts(id) ON DELETE CASCADE,
 identity_stamp VARCHAR(64) NOT NULL,
 csrf VARCHAR(64) NOT NULL,
 expires_at DOUBLE PRECISION NOT NULL,
 created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS tv_pairings_expiry_idx ON cine_security.tv_pairings(expires_at);
CREATE INDEX IF NOT EXISTS tv_pairings_account_idx ON cine_security.tv_pairings(account_id);
CREATE INDEX IF NOT EXISTS tv_devices_account_idx ON cine_security.tv_devices(account_id);
CREATE INDEX IF NOT EXISTS tv_devices_expiry_idx ON cine_security.tv_devices(expires_at);
REVOKE ALL ON cine_security.tv_pairings,cine_security.tv_devices FROM PUBLIC,anon,authenticated;
ALTER TABLE cine_security.tv_pairings ENABLE ROW LEVEL SECURITY;
ALTER TABLE cine_security.tv_devices ENABLE ROW LEVEL SECURITY;
COMMIT;
