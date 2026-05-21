-- 005_multi_owner.sql
-- Adds family / multi-account support. Backwards-compatible:
--   * New tables: accounts, access_tokens, channel_identities
--   * Existing business tables gain owner_id INTEGER DEFAULT 1 (nullable, FK -> accounts)
--   * All existing rows are backfilled to owner_id = 1 (the default "jk" account)
-- Storage code that has not yet been ported can keep ignoring owner_id;
-- ported code filters by owner_id.

CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default owner as id=1 so existing rows (backfilled via DEFAULT 1) line up.
INSERT INTO accounts (id, name, display_name)
VALUES (1, 'jk', 'JK')
ON CONFLICT (id) DO NOTHING;
SELECT setval('accounts_id_seq', GREATEST((SELECT MAX(id) FROM accounts), 1));

CREATE TABLE IF NOT EXISTS access_tokens (
    id SERIAL PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    owner_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    label TEXT,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tokens_active ON access_tokens(token) WHERE revoked_at IS NULL;

-- External identities (Telegram/Discord/Withings) -> owner mapping.
CREATE TABLE IF NOT EXISTS channel_identities (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    channel VARCHAR(16) NOT NULL,
    external_id TEXT NOT NULL,
    UNIQUE(channel, external_id)
);

-- Add owner_id to every per-person business table.
-- Shared/dictionary tables (finance_merchant_categories, import staging
-- chatgpt/claude/gemini/demo) are intentionally left alone.
ALTER TABLE raw_conversations     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE conversation_turns    ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE event_log             ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE session_meta          ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE session_tags          ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE session_summaries     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE observations          ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE hypotheses            ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE current_profile       ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE user_profile          ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE user_model            ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE strategies            ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE relationships         ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE trajectory_summary    ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE review_log            ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE finance_transactions  ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE withings_tokens       ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE withings_measures     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE withings_activity     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE withings_sleep        ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE withings_sync_log     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE proactive_log         ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE memory_embeddings     ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE memory_snapshot       ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE memory_clusters       ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE fact_edges            ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);
ALTER TABLE outsource_tasks       ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT 1 REFERENCES accounts(id);

-- Indexes for the tables we wire up first (observations, user_profile,
-- current_profile). Other tables get indexes when their storage layer is ported.
CREATE INDEX IF NOT EXISTS idx_obs_owner          ON observations(owner_id);
CREATE INDEX IF NOT EXISTS idx_up_owner           ON user_profile(owner_id);
CREATE INDEX IF NOT EXISTS idx_curprof_owner      ON current_profile(owner_id);
