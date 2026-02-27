-- Add metadata columns to enchants table
-- These were previously stored as effect lines in the YAML but are not real effects.

ALTER TABLE enchants ADD COLUMN IF NOT EXISTS restriction TEXT;
ALTER TABLE enchants ADD COLUMN IF NOT EXISTS binding BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE enchants ADD COLUMN IF NOT EXISTS guaranteed_success BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE enchants ADD COLUMN IF NOT EXISTS activation TEXT;
ALTER TABLE enchants ADD COLUMN IF NOT EXISTS credit TEXT;
