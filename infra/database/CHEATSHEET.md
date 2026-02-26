# PostgreSQL Cheatsheet

## Connect

```bash
# Via docker compose
docker compose exec db psql -U mabinogi -d mabinogi

# Direct (local dev defaults)
psql -h localhost -p 5432 -U mabinogi -d mabinogi
```

## Quick Inspection

```sql
-- List all tables
\dt

-- Describe a table (columns, types, constraints)
\d listings
\d enchants

-- Row counts for all tables
SELECT schemaname, relname, n_live_tup
FROM pg_stat_user_tables ORDER BY relname;
```

## Dictionary Tables

```sql
-- Game items
SELECT count(*) FROM game_items;
SELECT * FROM game_items WHERE name ILIKE '%드래곤%' LIMIT 10;

-- Enchants (slot: 0=접두, 1=접미)
SELECT count(*) FROM enchants;
SELECT id, slot, name, rank FROM enchants WHERE name = '노련한';

-- Enchant effects for a specific enchant
SELECT ee.effect_order, ee.raw_text, ee.min_value, ee.max_value, e.name AS effect_name
FROM enchant_effects ee
LEFT JOIN effects e ON e.id = ee.effect_id
WHERE ee.enchant_id = 42
ORDER BY ee.effect_order;

-- Effects dictionary
SELECT * FROM effects ORDER BY name LIMIT 20;

-- Reforge options
SELECT count(*) FROM reforge_options;
SELECT * FROM reforge_options WHERE option_name ILIKE '%대미지%' LIMIT 10;
```

## Listings

```sql
-- All listings with game item + enchant names
SELECT l.id, l.name, gi.name AS game_item,
       pe.name AS prefix, se.name AS suffix,
       l.item_type, l.item_grade, l.erg_grade, l.erg_level,
       l.created_at
FROM listings l
LEFT JOIN game_items gi ON gi.id = l.game_item_id
LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
ORDER BY l.id DESC;

-- Listing with rolled enchant effect values
SELECT l.name, ee.raw_text, ee.min_value, ee.max_value, lee.value AS rolled
FROM listing_enchant_effects lee
JOIN enchant_effects ee ON ee.id = lee.enchant_effect_id
JOIN listings l ON l.id = lee.listing_id
WHERE lee.listing_id = 1
ORDER BY ee.effect_order;

-- Listing reforge options
SELECT l.name, lro.option_name, lro.level, lro.max_level
FROM listing_reforge_options lro
JOIN listings l ON l.id = lro.listing_id
WHERE lro.listing_id = 1
ORDER BY lro.id;
```

## OCR Corrections

```sql
-- Pending corrections
SELECT id, original_text, corrected_text, section, ocr_model, charset_mismatch
FROM ocr_corrections
WHERE status = 'pending'
ORDER BY id DESC LIMIT 20;

-- Corrections by session
SELECT * FROM ocr_corrections WHERE session_id = 'your-session-id';
```

## Maintenance

```sql
-- Truncate all listing data (keeps dictionaries)
TRUNCATE listings, listing_enchant_effects, listing_reforge_options, ocr_corrections RESTART IDENTITY CASCADE;

-- Truncate everything (full reset, re-run import_dictionaries.py after)
TRUNCATE enchants, effects, enchant_effects, reforge_options, game_items,
         listings, listing_enchant_effects, listing_reforge_options, ocr_corrections
RESTART IDENTITY CASCADE;

-- Check foreign key references
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f' AND conrelid::regclass::text = 'listings';
```

## Useful psql Commands

```
\l          -- list databases
\dt         -- list tables
\d TABLE    -- describe table
\x          -- toggle expanded display (vertical output)
\timing     -- toggle query timing
\q          -- quit
```
