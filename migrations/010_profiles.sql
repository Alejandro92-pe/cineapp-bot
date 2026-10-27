-- Review before deployment; not executed by the application in production.
BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.profiles (
    account_id VARCHAR(36) PRIMARY KEY REFERENCES cine_security.accounts(id) ON DELETE CASCADE,
    avatar VARCHAR(16) NOT NULL CHECK (avatar IN ('tg','fox','wolf','dragon','ghost','cat','alien','robot','ninja')),
    updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS cine_security.saved_items (
    account_id VARCHAR(36) NOT NULL REFERENCES cine_security.accounts(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL,
    saved INTEGER NOT NULL CHECK (saved IN (0,1)),
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (account_id, content_id)
);
REVOKE ALL ON cine_security.profiles, cine_security.saved_items FROM PUBLIC, anon, authenticated;
ALTER TABLE cine_security.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE cine_security.saved_items ENABLE ROW LEVEL SECURITY;
COMMIT;
