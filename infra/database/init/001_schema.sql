-- Enchant definitions (from enchant.yaml)
CREATE TABLE IF NOT EXISTS enchants (
    id SERIAL PRIMARY KEY,
    slot SMALLINT NOT NULL CHECK (slot IN (0, 1)),  -- 0=접두, 1=접미
    name TEXT NOT NULL,
    rank SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 15),  -- 1..9 numeric, 10..15 = A..F
    header_text TEXT NOT NULL UNIQUE,                -- FM matching key: '[접두] 파동 (랭크 8)'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, rank, slot)
);

-- 68 unique effect names (마법 공격력, 크리티컬, etc.)
CREATE TABLE IF NOT EXISTS effects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_pct BOOLEAN NOT NULL DEFAULT FALSE,           -- TRUE for % effects (수리비, 성공률)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- What effects each enchant has (with conditions and value ranges)
CREATE TABLE IF NOT EXISTS enchant_effects (
    id SERIAL PRIMARY KEY,
    enchant_id INTEGER NOT NULL REFERENCES enchants(id) ON DELETE CASCADE,
    effect_id INTEGER REFERENCES effects(id) ON DELETE RESTRICT,  -- NULL for restrictions/flags
    effect_order INTEGER NOT NULL,
    condition_text TEXT,                              -- NULL = unconditional
    min_value NUMERIC,                               -- signed: +8 or -5. NULL for non-valued
    max_value NUMERIC,                               -- same as min = fixed. NULL for non-valued
    raw_text TEXT NOT NULL,                           -- original text for display
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (enchant_id, effect_order)
);

-- Items
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Which enchant is applied to an item
CREATE TABLE IF NOT EXISTS item_enchants (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    enchant_id INTEGER NOT NULL REFERENCES enchants(id) ON DELETE RESTRICT,
    slot SMALLINT NOT NULL CHECK (slot IN (0, 1)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (item_id, slot)                           -- one prefix + one suffix per item
);

-- Actual rolled values for each effect on an item
CREATE TABLE IF NOT EXISTS item_enchant_effects (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    enchant_effect_id INTEGER NOT NULL REFERENCES enchant_effects(id) ON DELETE RESTRICT,
    value NUMERIC NOT NULL,                          -- signed: the actual rolled number
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reforge options
CREATE TABLE IF NOT EXISTS reforge_options (
    id SERIAL PRIMARY KEY,
    option_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger function for updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enchants_updated_at ON enchants;
CREATE TRIGGER trg_enchants_updated_at
BEFORE UPDATE ON enchants
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_effects_updated_at ON effects;
CREATE TRIGGER trg_effects_updated_at
BEFORE UPDATE ON effects
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_enchant_effects_updated_at ON enchant_effects;
CREATE TRIGGER trg_enchant_effects_updated_at
BEFORE UPDATE ON enchant_effects
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_items_updated_at ON items;
CREATE TRIGGER trg_items_updated_at
BEFORE UPDATE ON items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_reforge_options_updated_at ON reforge_options;
CREATE TRIGGER trg_reforge_options_updated_at
BEFORE UPDATE ON reforge_options
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
