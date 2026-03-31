CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    model VARCHAR(200),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    source VARCHAR(50) DEFAULT 'chat'
);

CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage (created_at);
