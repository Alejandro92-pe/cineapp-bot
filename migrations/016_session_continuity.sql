-- Review locally first. Viewing lasts seven days; admin elevation still one hour.
BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.admin_leases (
 token_hash varchar(64) PRIMARY KEY REFERENCES cine_security.sessions(token_hash) ON DELETE CASCADE,
 expires_at double precision NOT NULL
);
ALTER TABLE cine_security.admin_leases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.admin_leases FROM PUBLIC, anon, authenticated;
-- Preserve current admin deadlines. Only newly migrated, unexpired sessions extend.
WITH migrated AS (
 INSERT INTO cine_security.admin_leases
 SELECT token_hash, expires_at FROM cine_security.sessions
 WHERE admin=1 AND expires_at>extract(epoch FROM now())
 ON CONFLICT DO NOTHING RETURNING token_hash
)
UPDATE cine_security.sessions SET admin=0, expires_at=greatest(expires_at,extract(epoch FROM now())+604800)
WHERE token_hash IN (SELECT token_hash FROM migrated);
COMMIT;
