-- 012_drop_2fa.sql
-- Drop the unused TOTP / 2FA columns. The chosen security model is
-- "admin approves each new device" (see migration 011), not "user enters
-- 6-digit code at login". Leaving the columns around is dead schema.

ALTER TABLE accounts       DROP COLUMN IF EXISTS requires_2fa;
ALTER TABLE accounts       DROP COLUMN IF EXISTS totp_secret;
ALTER TABLE accounts       DROP COLUMN IF EXISTS totp_enrolled_at;
ALTER TABLE access_tokens  DROP COLUMN IF EXISTS last_2fa_at;
