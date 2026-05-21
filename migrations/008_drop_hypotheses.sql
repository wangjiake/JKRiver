-- 008_drop_hypotheses.sql
-- Remove the hypotheses table and its storage module — replaced entirely by
-- user_profile (layer 'suspected'/'confirmed' + supersedes/superseded_by +
-- evidence JSONB). The table has been empty (0 rows) and no production code
-- reads or writes it; only tests/test_storage.py referenced it.

DROP TABLE IF EXISTS hypotheses CASCADE;
