-- 007_token_usage_owner.sql
-- The token_usage table (created in 004_token_usage.sql) was missed by 005's
-- bulk owner_id rollout. This migration adds it so each family member can see
-- their own token consumption.

ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);

CREATE INDEX IF NOT EXISTS idx_token_usage_owner_created
    ON token_usage(owner_id, created_at DESC);
