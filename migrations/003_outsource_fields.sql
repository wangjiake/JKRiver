-- Add session_id, pending_question, deleted_at to outsource_tasks
-- Also update status comment to include 'cancelled'
ALTER TABLE outsource_tasks
    ADD COLUMN IF NOT EXISTS session_id VARCHAR(64) DEFAULT '',
    ADD COLUMN IF NOT EXISTS pending_question TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;
