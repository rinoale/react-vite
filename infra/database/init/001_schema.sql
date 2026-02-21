CREATE TABLE IF NOT EXISTS enchant_entries (
    id BIGSERIAL PRIMARY KEY,
    slot TEXT NOT NULL CHECK (slot IN ('prefix', 'suffix')),
    name TEXT NOT NULL,
    rank TEXT NOT NULL,
    header_text TEXT NOT NULL UNIQUE,
    source_file TEXT NOT NULL DEFAULT 'data/dictionary/enchant.txt',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS enchant_effects (
    id BIGSERIAL PRIMARY KEY,
    enchant_entry_id BIGINT NOT NULL REFERENCES enchant_entries(id) ON DELETE CASCADE,
    effect_order INTEGER NOT NULL,
    text TEXT NOT NULL,
    option_name TEXT,
    option_level INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (enchant_entry_id, effect_order)
);

CREATE TABLE IF NOT EXISTS reforge_options (
    id BIGSERIAL PRIMARY KEY,
    option_name TEXT NOT NULL UNIQUE,
    source_file TEXT NOT NULL DEFAULT 'data/dictionary/reforge.txt',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enchant_entries_updated_at ON enchant_entries;
CREATE TRIGGER trg_enchant_entries_updated_at
BEFORE UPDATE ON enchant_entries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_enchant_effects_updated_at ON enchant_effects;
CREATE TRIGGER trg_enchant_effects_updated_at
BEFORE UPDATE ON enchant_effects
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_reforge_options_updated_at ON reforge_options;
CREATE TRIGGER trg_reforge_options_updated_at
BEFORE UPDATE ON reforge_options
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
