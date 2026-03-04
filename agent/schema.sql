BEGIN;

CREATE TABLE IF NOT EXISTS chatgpt (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    data_type VARCHAR(50),
    format VARCHAR(50),
    content JSONB,
    file_path TEXT,
    checksum VARCHAR(128),
    status VARCHAR(50) DEFAULT 'pending',
    conversation_time TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claude (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    data_type VARCHAR(50),
    format VARCHAR(50),
    content JSONB,
    file_path TEXT,
    checksum VARCHAR(128),
    status VARCHAR(50) DEFAULT 'pending',
    conversation_time TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gemini (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    data_type VARCHAR(50),
    format VARCHAR(50),
    content JSONB,
    file_path TEXT,
    checksum VARCHAR(128),
    status VARCHAR(50) DEFAULT 'pending',
    conversation_time TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    data_type VARCHAR(50),
    format VARCHAR(50),
    content JSONB,
    file_path TEXT,
    checksum VARCHAR(128),
    status VARCHAR(50) DEFAULT 'pending',
    conversation_time TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    session_created_at TIMESTAMPTZ,
    user_input TEXT,
    user_input_at TIMESTAMPTZ,
    assistant_reply TEXT,
    assistant_reply_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raw_conv_session ON raw_conversations(session_id);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    session_created_at TIMESTAMPTZ,
    user_input TEXT,
    user_input_at TIMESTAMPTZ,
    assistant_reply TEXT,
    assistant_reply_at TIMESTAMPTZ,
    intent TEXT,
    need_memory BOOLEAN,
    memory_type TEXT,
    ai_summary TEXT,
    perception_at TIMESTAMPTZ,
    memories_used JSONB,
    memories_used_at TIMESTAMPTZ,
    raw_response TEXT,
    raw_response_at TIMESTAMPTZ,
    verification_result TEXT,
    verification_result_at TIMESTAMPTZ,
    final_response TEXT,
    final_response_at TIMESTAMPTZ,
    thinking_notes TEXT,
    thinking_notes_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    has_new_info BOOLEAN DEFAULT true,
    input_type VARCHAR(16),
    file_path TEXT,
    file_data BYTEA,
    tool_results JSONB
);

CREATE INDEX IF NOT EXISTS idx_conv_turns_session ON conversation_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_turns_input_at ON conversation_turns(user_input_at DESC);

CREATE TABLE IF NOT EXISTS event_log (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5,
    session_id VARCHAR(64),
    decay_days INTEGER,
    expires_at TIMESTAMPTZ,
    source_session VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_category ON event_log(category);
CREATE INDEX IF NOT EXISTS idx_event_active ON event_log(expires_at) WHERE expires_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_importance ON event_log(importance DESC);

CREATE TABLE IF NOT EXISTS session_tags (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    tag TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_tags_session ON session_tags(session_id);
CREATE INDEX IF NOT EXISTS idx_session_tags_tag ON session_tags(tag);

CREATE TABLE IF NOT EXISTS session_summaries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    intent_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    observation_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    subject TEXT,
    context TEXT,
    source_turn_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rejected BOOLEAN DEFAULT FALSE,
    note TEXT,
    classification VARCHAR(32)
);

CREATE INDEX IF NOT EXISTS idx_obs_session ON observations(session_id);
CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_subject ON observations(subject);

CREATE TABLE IF NOT EXISTS hypotheses (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    claim TEXT NOT NULL,
    evidence_for JSONB DEFAULT '[]',
    evidence_against JSONB DEFAULT '[]',
    confidence FLOAT DEFAULT 0.5,
    mention_count INTEGER DEFAULT 1,
    status VARCHAR(16) DEFAULT 'pending',
    source_type VARCHAR(16) DEFAULT 'stated',
    decay_days INTEGER,
    expires_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    suspected_value TEXT,
    suspected_confidence FLOAT DEFAULT 0,
    suspected_since TIMESTAMPTZ,
    suspected_evidence JSONB DEFAULT '[]',
    history JSONB DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_hyp_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_hyp_category ON hypotheses(category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hyp_cat_subject ON hypotheses(category, subject) WHERE status IN ('pending', 'active', 'established');
CREATE INDEX IF NOT EXISTS idx_hyp_mention_count ON hypotheses(mention_count DESC);

CREATE TABLE IF NOT EXISTS current_profile (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    hypothesis_id INTEGER REFERENCES hypotheses(id),
    confirmed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profile_category ON current_profile(category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_cat_field_value ON current_profile(category, field, value);

CREATE TABLE IF NOT EXISTS user_profile (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    value TEXT NOT NULL,
    layer VARCHAR(16) DEFAULT 'suspected',
    source_type VARCHAR(16) DEFAULT 'stated',
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    decay_days INTEGER,
    expires_at TIMESTAMPTZ,
    evidence JSONB DEFAULT '[]',
    mention_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    superseded_by INTEGER REFERENCES user_profile(id),
    supersedes INTEGER REFERENCES user_profile(id),
    rejected BOOLEAN DEFAULT FALSE,
    human_end_time TIMESTAMPTZ,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_up_layer ON user_profile(layer);
CREATE INDEX IF NOT EXISTS idx_up_category ON user_profile(category);
CREATE INDEX IF NOT EXISTS idx_up_current ON user_profile(category, subject) WHERE end_time IS NULL;
CREATE INDEX IF NOT EXISTS idx_up_active ON user_profile(layer, end_time) WHERE end_time IS NULL;
CREATE INDEX IF NOT EXISTS idx_up_rejected ON user_profile(rejected) WHERE rejected = TRUE;

CREATE TABLE IF NOT EXISTS user_model (
    id SERIAL PRIMARY KEY,
    dimension TEXT NOT NULL UNIQUE,
    assessment TEXT NOT NULL,
    evidence_summary TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    hypothesis_category TEXT NOT NULL,
    hypothesis_subject TEXT NOT NULL,
    strategy_type VARCHAR(32) NOT NULL,
    description TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    approach TEXT NOT NULL,
    priority FLOAT DEFAULT 0.5,
    status VARCHAR(16) DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_strat_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strat_hypothesis ON strategies(hypothesis_category, hypothesis_subject);

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    name TEXT,
    relation TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    first_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    last_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    mention_count INTEGER DEFAULT 1,
    status VARCHAR(16) DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_rel_status ON relationships(status);
CREATE INDEX IF NOT EXISTS idx_rel_name ON relationships(name);
CREATE INDEX IF NOT EXISTS idx_rel_relation ON relationships(relation);

CREATE TABLE IF NOT EXISTS trajectory_summary (
    id SERIAL PRIMARY KEY,
    life_phase TEXT NOT NULL,
    phase_characteristics TEXT NOT NULL,
    trajectory_direction TEXT NOT NULL,
    stability_assessment TEXT NOT NULL,
    key_anchors JSONB DEFAULT '[]',
    volatile_areas JSONB DEFAULT '[]',
    recent_momentum TEXT,
    predicted_shifts TEXT,
    full_summary TEXT,
    session_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_log (
    id SERIAL PRIMARY KEY,
    target_table VARCHAR(32) NOT NULL,
    target_id INTEGER NOT NULL,
    action VARCHAR(32) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_log_target ON review_log(target_table, target_id);

CREATE TABLE IF NOT EXISTS finance_transactions (
    id SERIAL PRIMARY KEY,
    transaction_date TIMESTAMPTZ NOT NULL,
    merchant TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'JPY',
    amount_jpy NUMERIC(12, 2),
    category TEXT,
    card_name TEXT DEFAULT 'credit_card',
    email_id TEXT UNIQUE,
    note TEXT,
    metadata JSONB DEFAULT '{}',
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ft_date ON finance_transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_ft_merchant ON finance_transactions(merchant);
CREATE INDEX IF NOT EXISTS idx_ft_category ON finance_transactions(category);

CREATE TABLE IF NOT EXISTS finance_merchant_categories (
    id SERIAL PRIMARY KEY,
    merchant_pattern TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS withings_tokens (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    scope TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS withings_measures (
    id SERIAL PRIMARY KEY,
    withings_grpid BIGINT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL,
    measure_type INTEGER NOT NULL,
    value NUMERIC(12, 4) NOT NULL,
    unit TEXT,
    source INTEGER,
    metadata JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(withings_grpid, measure_type)
);

CREATE INDEX IF NOT EXISTS idx_wm_type_date ON withings_measures(measure_type, measured_at DESC);

CREATE TABLE IF NOT EXISTS withings_activity (
    id SERIAL PRIMARY KEY,
    activity_date DATE NOT NULL UNIQUE,
    steps INTEGER,
    distance NUMERIC(10,2),
    calories NUMERIC(10,2),
    active_calories NUMERIC(10,2),
    soft_activity_duration INTEGER,
    moderate_activity_duration INTEGER,
    intense_activity_duration INTEGER,
    metadata JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wa_date ON withings_activity(activity_date DESC);

CREATE TABLE IF NOT EXISTS withings_sleep (
    id SERIAL PRIMARY KEY,
    sleep_date DATE NOT NULL UNIQUE,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds INTEGER,
    awake_seconds INTEGER,
    wakeup_count INTEGER,
    sleep_score INTEGER,
    hr_average INTEGER,
    hr_min INTEGER,
    rr_average INTEGER,
    metadata JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ws_date ON withings_sleep(sleep_date DESC);

CREATE TABLE IF NOT EXISTS withings_sync_log (
    id SERIAL PRIMARY KEY,
    data_type TEXT NOT NULL,
    last_sync_at TIMESTAMPTZ NOT NULL,
    records_synced INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wsl_type ON withings_sync_log(data_type, created_at DESC);

CREATE TABLE IF NOT EXISTS proactive_log (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_ref TEXT,
    message_text TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proactive_log_chat_sent ON proactive_log(chat_id, sent_at DESC);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id SERIAL PRIMARY KEY,
    source_table VARCHAR(32) NOT NULL,
    source_id INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    text_content TEXT NOT NULL,
    embedding JSONB NOT NULL,
    model VARCHAR(64) DEFAULT 'bge-m3',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_table, source_id)
);

CREATE TABLE IF NOT EXISTS memory_snapshot (
    id SERIAL PRIMARY KEY,
    snapshot_text TEXT NOT NULL,
    profile_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_edges (
    id SERIAL PRIMARY KEY,
    source_fact_id INTEGER NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    target_fact_id INTEGER NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    edge_type VARCHAR(32) NOT NULL,
    description TEXT,
    confidence FLOAT DEFAULT 0.8,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_fact_id, target_fact_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_fe_source ON fact_edges(source_fact_id);
CREATE INDEX IF NOT EXISTS idx_fe_target ON fact_edges(target_fact_id);

CREATE TABLE IF NOT EXISTS memory_clusters (
    id SERIAL PRIMARY KEY,
    cluster_index INTEGER NOT NULL,
    theme TEXT,
    centroid JSONB NOT NULL,
    member_ids JSONB NOT NULL DEFAULT '[]',
    member_count INTEGER DEFAULT 0,
    representative_text TEXT,
    embeddings_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
