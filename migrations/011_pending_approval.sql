-- 011_pending_approval.sql
-- Admin-approval gate for newly-accepted invites.
--
-- When settings.yaml `family.require_admin_approval` is on, accepting an
-- invite mints a token row with pending_approval=TRUE. The cookie is set
-- but identity.resolve_owner_id refuses pending tokens (they behave like
-- revoked ones). The accept page polls until admin approves, then auto-
-- redirects to /chat.

ALTER TABLE access_tokens ADD COLUMN IF NOT EXISTS pending_approval BOOLEAN DEFAULT FALSE;

-- Existing rows are not pending (they were created when this concept didn't
-- exist) — the DEFAULT FALSE handles new rows, leave old rows as-is.
UPDATE access_tokens SET pending_approval = FALSE WHERE pending_approval IS NULL;

CREATE INDEX IF NOT EXISTS idx_access_tokens_pending
    ON access_tokens(pending_approval) WHERE pending_approval = TRUE;
