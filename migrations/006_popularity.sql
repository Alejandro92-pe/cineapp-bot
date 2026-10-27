-- LOCAL REVIEW ONLY. Not applied to Supabase.
BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.playback_opens (
    account_id VARCHAR(36) NOT NULL REFERENCES cine_security.accounts(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL,
    day INTEGER NOT NULL,
    PRIMARY KEY (account_id, content_id, day)
);
CREATE INDEX IF NOT EXISTS playback_opens_day_content ON cine_security.playback_opens(day, content_id);
REVOKE ALL ON cine_security.playback_opens FROM PUBLIC, anon, authenticated;
ALTER TABLE cine_security.playback_opens ENABLE ROW LEVEL SECURITY;
COMMIT;
