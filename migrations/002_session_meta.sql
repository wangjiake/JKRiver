-- Migration: Add session_meta table for pinning, renaming, and soft-deleting sessions
CREATE TABLE IF NOT EXISTS session_meta (
    session_id VARCHAR(64) PRIMARY KEY,
    custom_name TEXT,
    pinned BOOLEAN DEFAULT FALSE,
    pinned_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
