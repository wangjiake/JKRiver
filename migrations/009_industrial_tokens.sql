-- 009_industrial_tokens.sql
-- Industrial-grade family token model: hash-stored secrets, device metadata,
-- invite flow, and audit log. Backwards-compatible — existing plaintext tokens
-- are hashed in place so old cookies keep working.

-- ── 0. extensions needed ────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- for DIGEST(..., 'sha256')


-- ── 1. access_tokens: hash + device metadata ────────────────────────────

ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS token_hash    VARCHAR(64);
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS token_prefix  VARCHAR(12);
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS device_type   VARCHAR(16);   -- mobile/desktop/tablet/bot/unknown
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS device_name   TEXT;          -- user-editable friendly name
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS last_ua       TEXT;
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS last_ip       TEXT;

-- Backfill: SHA-256 existing plaintext tokens. Old cookies still match because
-- the verification path will hash the incoming cookie value before lookup.
UPDATE access_tokens
   SET token_hash   = ENCODE(DIGEST(token, 'sha256'), 'hex'),
       token_prefix = LEFT(token, 8)
 WHERE token_hash IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_access_tokens_hash ON access_tokens(token_hash);
CREATE INDEX        IF NOT EXISTS idx_access_tokens_active
    ON access_tokens(token_hash) WHERE revoked_at IS NULL;


-- ── 2. family_invites: one-time invite links ────────────────────────────

CREATE TABLE IF NOT EXISTS family_invites (
    id          SERIAL PRIMARY KEY,
    invite_uuid VARCHAR(64) NOT NULL UNIQUE,           -- the URL slug
    owner_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    label       TEXT,                                  -- admin's hint for who this is
    created_by  INTEGER NOT NULL REFERENCES accounts(id),
    expires_at  TIMESTAMPTZ NOT NULL,                  -- typically NOW() + 24h
    used_at     TIMESTAMPTZ,                           -- NULL until consumed
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_family_invites_active
    ON family_invites(invite_uuid) WHERE used_at IS NULL;


-- ── 3. family_audit: who did what when ──────────────────────────────────

CREATE TABLE IF NOT EXISTS family_audit (
    id           SERIAL PRIMARY KEY,
    actor_owner_id  INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    target_owner_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    action       VARCHAR(48) NOT NULL,                 -- member.created / device.signed_out / invite.accepted etc.
    target_type  VARCHAR(32),                          -- 'member' / 'device' / 'invite' / 'channel'
    target_id    INTEGER,
    details      JSONB DEFAULT '{}',
    ip           TEXT,
    at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_family_audit_at ON family_audit(at DESC);
CREATE INDEX IF NOT EXISTS idx_family_audit_actor ON family_audit(actor_owner_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_family_audit_target ON family_audit(target_owner_id, at DESC);
