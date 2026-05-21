-- 006_owner_unique.sql
-- Rebuild UNIQUE constraints that need owner_id, so sleep's upsert paths
-- (user_model.dimension, current_profile.(category, field, value)) work
-- correctly across owners. Without these the second owner's UPSERT silently
-- merges into the first owner's row.

-- user_model: drop the old UNIQUE(dimension) constraint, add UNIQUE(owner_id, dimension).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'user_model_dimension_key'
          AND conrelid = 'user_model'::regclass
    ) THEN
        ALTER TABLE user_model DROP CONSTRAINT user_model_dimension_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_model_owner_dim
    ON user_model(owner_id, dimension);

-- current_profile: replace UNIQUE(category, field, value) with composite key.
DROP INDEX IF EXISTS idx_profile_cat_field_value;
CREATE UNIQUE INDEX IF NOT EXISTS uq_curprof_owner_cat_field_value
    ON current_profile(owner_id, category, field, value);
