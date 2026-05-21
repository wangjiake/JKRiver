-- 010_2fa_geoip.sql
-- Adds two-factor authentication (TOTP) per-member and geolocation tracking.
--
-- 2FA flow (handled in app, not SQL):
--   admin enables 2FA → server generates TOTP secret → user scans QR with
--   authenticator app → user enters 6-digit code → enrolled. Subsequent
--   logins require both the device cookie AND a current 6-digit code (proven
--   within the last 24h via the `jkriver_2fa_until` cookie).
--
-- Geolocation: every login (and periodic activity-tracking touch) checks
-- the IP against `geoip_cache`; cache miss triggers a best-effort ipinfo.io
-- lookup. Result is written to both the cache (so a busy IP isn't looked up
-- repeatedly) and to access_tokens.last_country / last_city for UI display.
-- A row is appended to access_log only when the city *changes* for that
-- device (avoids per-request log noise).

-- ── 1. accounts: per-member 2FA ──────────────────────────────────────────

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS requires_2fa     BOOLEAN DEFAULT FALSE;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS totp_secret      TEXT;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS totp_enrolled_at TIMESTAMPTZ;


-- ── 2. access_tokens: last-known geolocation per device ──────────────────

ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS last_country VARCHAR(8);   -- ISO-3166 alpha-2
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS last_city    TEXT;
ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS last_2fa_at  TIMESTAMPTZ;  -- when this device last passed 2FA


-- ── 3. geoip_cache: shared IP→city/country lookup cache ─────────────────

CREATE TABLE IF NOT EXISTS geoip_cache (
    ip          TEXT PRIMARY KEY,
    country     VARCHAR(8),
    city        TEXT,
    region      TEXT,
    raw         JSONB DEFAULT '{}',
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geoip_fetched ON geoip_cache(fetched_at DESC);


-- ── 4. access_log: append-only record of notable login events ───────────
--
-- Only written when one of these happens:
--   * a new device first appears (invite accepted)
--   * an existing device shows up from a different city than its prior one
--   * a 2FA verification succeeds or fails

CREATE TABLE IF NOT EXISTS access_log (
    id          SERIAL PRIMARY KEY,
    owner_id    INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    token_id    INTEGER REFERENCES access_tokens(id) ON DELETE SET NULL,
    event       VARCHAR(32) NOT NULL,        -- 'new_device' / 'new_location' / '2fa_pass' / '2fa_fail' / 'sign_out'
    ip          TEXT,
    country     VARCHAR(8),
    city        TEXT,
    details     JSONB DEFAULT '{}',
    at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_log_owner_at ON access_log(owner_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_access_log_at       ON access_log(at DESC);
