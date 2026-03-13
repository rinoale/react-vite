#!/usr/bin/env python3
"""Import source-of-truth YAML files into PostgreSQL.

Modes:
  (default)    Upsert — insert new rows, update existing, report counts.
  --fresh      Truncate dictionary tables first, then plain insert.
  --dry-run    Run upsert logic but rollback — shows what would change.
"""
import argparse
import hashlib
import re
from pathlib import Path
from typing import Iterable

import yaml
from sqlalchemy import create_engine, text
from uuid_utils import uuid7


HEADER_RE = re.compile(r"^\[(접두|접미)\]\s+(.+?)\s+\(랭크\s+([^)]+)\)$")
RANK_LETTER_TO_INT = {
    "A": 10,
    "B": 11,
    "C": 12,
    "D": 13,
    "E": 14,
    "F": 15,
}

# Matches: <effect_name> <value> [~ <value>] [%] <증가|감소>
VALUED_EFFECT_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<min>\d+(?:\.\d+)?)"
    r"(?:\s*~\s*(?P<max>\d+(?:\.\d+)?))?"
    r"\s*%?\s+"
    r"(?P<dir>증가|감소)\s*$"
)

CONDITION_RE = re.compile(r"^(?P<cond>.+?때)\s*,?\s*(?P<effect>.+)$")

SEED_ROLES = ["master", "admin"]
SEED_FEATURE_FLAGS = ["manage_tags", "manage_corrections"]

DICT_TABLES = [
    "enchant_effects", "enchants", "effects",
    "reforge_options", "echostone_options", "murias_relic_options",
    "game_items",
]


# ── Helpers ──

def _db_url_from_args(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url
    return (
        f"postgresql+psycopg2://{args.db_user}:{args.db_password}"
        f"@{args.db_host}:{args.db_port}/{args.db_name}"
    )


def _rank_to_int(rank_str: str) -> int:
    r = RANK_LETTER_TO_INT.get(rank_str.upper())
    return r if r is not None else int(rank_str)


def chunked(items: Iterable, size: int) -> Iterable[list]:
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


class ImportStats:
    """Track inserted/updated/skipped counts per table."""

    def __init__(self):
        self._data: dict[str, dict[str, int]] = {}

    def record(self, table: str, action: str):
        t = self._data.setdefault(table, {"inserted": 0, "updated": 0, "skipped": 0})
        t[action] += 1

    def total(self, table: str) -> int:
        t = self._data.get(table, {})
        return t.get("inserted", 0) + t.get("updated", 0) + t.get("skipped", 0)

    def print_report(self):
        for table, counts in self._data.items():
            parts = []
            if counts["inserted"]:
                parts.append(f"{counts['inserted']} inserted")
            if counts["updated"]:
                parts.append(f"{counts['updated']} updated")
            if counts["skipped"]:
                parts.append(f"{counts['skipped']} unchanged")
            if parts:
                print(f"  {table}: {', '.join(parts)}")

    def summary_line(self) -> str:
        totals = []
        for table, counts in self._data.items():
            total = counts["inserted"] + counts["updated"] + counts["skipped"]
            totals.append(f"{table}={total}")
        return ", ".join(totals)


def _upsert(conn, insert_sql: str, update_sql: str, params: dict, stats: ImportStats, table: str):
    """Try insert; on conflict, compare and update if changed."""
    result = conn.execute(text(insert_sql), params)
    if result.rowcount > 0:
        stats.record(table, "inserted")
    else:
        # Row exists — check if update changes anything
        result = conn.execute(text(update_sql), params)
        if result.rowcount > 0:
            stats.record(table, "updated")
        else:
            stats.record(table, "skipped")


# ── Parsers ──

def parse_effects_file(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return [{"id": entry["id"], "name": entry["name"], "is_pct": entry["is_pct"]} for entry in data]


def parse_enchant(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    entries: list[dict] = []
    for item in data:
        slot_kr = item["slot"]
        slot = 0 if slot_kr == "접두" else 1
        rank_str = str(item["rank"])
        header_text = f"[{slot_kr}] {item['name']} (랭크 {rank_str})"
        entry = {
            "id": item["id"],
            "slot": slot,
            "name": item["name"],
            "rank": _rank_to_int(rank_str),
            "header_text": header_text,
            "effects": item.get("effects", []),
            "restriction": item.get("restriction"),
            "binding": item.get("binding", False),
            "guaranteed_success": item.get("guaranteed_success", False),
            "activation": item.get("activation"),
            "credit": item.get("credit"),
        }
        entries.append(entry)

    return entries


def parse_reforge(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    seen: set[str] = set()
    options: list[dict] = []
    for entries in data.values():
        for entry in entries:
            oid = entry["option_id"]
            if oid in seen:
                continue
            seen.add(oid)
            options.append({"id": oid, "option_name": entry["option_name"]})
    return options


def parse_game_items(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "type": entry.get("type"),
            "searchable": entry.get("searchable", False),
            "tradable": entry.get("tradable", True),
        }
        for entry in data
    ]


def parse_echostone(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def parse_murias_relic(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _split_condition(effect_text: str) -> tuple[str | None, str]:
    m = CONDITION_RE.match(effect_text)
    if m and m.group("effect"):
        return m.group("cond"), m.group("effect")
    return None, effect_text


def _parse_valued_effect(
    effect_text: str, effect_name_set: set[str]
) -> tuple[int | None, float | None, float | None]:
    m = VALUED_EFFECT_RE.match(effect_text.strip())
    if not m:
        return None, None, None

    raw_name = m.group("name").strip()
    min_val = float(m.group("min"))
    max_val = float(m.group("max")) if m.group("max") else min_val
    sign = 1 if m.group("dir") == "증가" else -1

    if raw_name in effect_name_set:
        return raw_name, sign * min_val, sign * max_val

    pct_name = f"{raw_name} (%)"
    if pct_name in effect_name_set:
        return pct_name, sign * min_val, sign * max_val

    return None, None, None


# ── Importers (fresh mode: plain INSERT) ──

def _insert_effects(conn, effects: list[dict]) -> dict[str, str]:
    name_to_id: dict[str, str] = {}
    for eff in effects:
        conn.execute(
            text("INSERT INTO effects (id, name, is_pct) VALUES (:id, :name, :is_pct)"),
            {"id": eff["id"], "name": eff["name"], "is_pct": eff["is_pct"]},
        )
        name_to_id[eff["name"]] = eff["id"]
    return name_to_id


def _insert_enchants(conn, enchant_entries: list[dict], effect_name_to_id: dict[str, str]) -> tuple[int, int]:
    effect_name_set = set(effect_name_to_id.keys())
    entry_count = 0
    link_count = 0

    for entry in enchant_entries:
        enchant_id = entry["id"]
        conn.execute(
            text(
                "INSERT INTO enchants (id, slot, name, rank, header_text, "
                "restriction, binding, guaranteed_success, activation, credit) "
                "VALUES (:id, :slot, :name, :rank, :header_text, "
                ":restriction, :binding, :guaranteed_success, :activation, :credit)"
            ),
            {
                "id": enchant_id, "slot": entry["slot"], "name": entry["name"],
                "rank": entry["rank"], "header_text": entry["header_text"],
                "restriction": entry.get("restriction"), "binding": entry.get("binding", False),
                "guaranteed_success": entry.get("guaranteed_success", False),
                "activation": entry.get("activation"), "credit": entry.get("credit"),
            },
        )
        entry_count += 1

        for idx, eff_item in enumerate(entry["effects"], start=1):
            condition_text = eff_item.get('condition')
            effect_text = eff_item['effect']
            raw_text = f"{condition_text} {effect_text}" if condition_text else effect_text
            _, min_val, max_val = _parse_valued_effect(effect_text, effect_name_set)
            conn.execute(
                text(
                    "INSERT INTO enchant_effects "
                    "(id, enchant_id, effect_id, effect_order, condition_text, min_value, max_value, raw_text) "
                    "VALUES (:id, :enchant_id, :effect_id, :effect_order, :condition_text, :min_value, :max_value, :raw_text)"
                ),
                {
                    "id": eff_item['id'], "enchant_id": enchant_id,
                    "effect_id": eff_item.get('effect_id'), "effect_order": idx,
                    "condition_text": condition_text,
                    "min_value": min_val, "max_value": max_val, "raw_text": raw_text,
                },
            )
            link_count += 1

    return entry_count, link_count


def _insert_reforge(conn, options: list[dict]) -> int:
    for option in options:
        conn.execute(
            text("INSERT INTO reforge_options (id, option_name) VALUES (:id, :option_name)"),
            {"id": option["id"], "option_name": option["option_name"]},
        )
    return len(options)


def _insert_game_items(conn, items: list[dict]) -> int:
    for batch in chunked(items, 500):
        for item in batch:
            conn.execute(
                text(
                    "INSERT INTO game_items (id, name, type, searchable, tradable) "
                    "VALUES (:id, :name, :type, :searchable, :tradable)"
                ),
                {
                    "id": item["id"], "name": item["name"], "type": item.get("type"),
                    "searchable": item.get("searchable", False), "tradable": item.get("tradable", True),
                },
            )
    return len(items)


def _insert_echostone(conn, entries: list[dict]) -> int:
    for entry in entries:
        conn.execute(
            text(
                "INSERT INTO echostone_options (id, option_name, type, max_level, min_level) "
                "VALUES (:id, :option_name, :type, :max_level, :min_level)"
            ),
            {
                "id": entry["id"], "option_name": entry["option_name"], "type": entry["type"],
                "max_level": entry.get("max_level"), "min_level": entry.get("min_level", 1),
            },
        )
    return len(entries)


def _insert_murias_relic(conn, entries: list[dict]) -> int:
    for entry in entries:
        conn.execute(
            text(
                "INSERT INTO murias_relic_options "
                "(id, option_name, type, max_level, min_level, value_per_level, option_unit) "
                "VALUES (:id, :option_name, :type, :max_level, :min_level, :value_per_level, :option_unit)"
            ),
            {
                "id": entry["id"], "option_name": entry["option_name"], "type": entry["type"],
                "max_level": entry.get("max_level"), "min_level": entry.get("min_level", 1),
                "value_per_level": entry.get("value_per_level"), "option_unit": entry.get("option_unit"),
            },
        )
    return len(entries)


# ── Importers (upsert mode: ON CONFLICT UPDATE, track stats) ──

def _upsert_effects(conn, effects: list[dict], stats: ImportStats) -> dict[str, str]:
    name_to_id: dict[str, str] = {}
    for eff in effects:
        _upsert(
            conn,
            "INSERT INTO effects (id, name, is_pct) VALUES (:id, :name, :is_pct) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE effects SET name = :name, is_pct = :is_pct "
            "WHERE id = :id AND (name != :name OR is_pct != :is_pct)",
            {"id": eff["id"], "name": eff["name"], "is_pct": eff["is_pct"]},
            stats, "effects",
        )
        name_to_id[eff["name"]] = eff["id"]
    return name_to_id


def _upsert_enchants(conn, enchant_entries: list[dict], effect_name_to_id: dict[str, str], stats: ImportStats) -> tuple[int, int]:
    effect_name_set = set(effect_name_to_id.keys())

    for entry in enchant_entries:
        enchant_id = entry["id"]
        params = {
            "id": enchant_id, "slot": entry["slot"], "name": entry["name"],
            "rank": entry["rank"], "header_text": entry["header_text"],
            "restriction": entry.get("restriction"), "binding": entry.get("binding", False),
            "guaranteed_success": entry.get("guaranteed_success", False),
            "activation": entry.get("activation"), "credit": entry.get("credit"),
        }
        _upsert(
            conn,
            "INSERT INTO enchants (id, slot, name, rank, header_text, "
            "restriction, binding, guaranteed_success, activation, credit) "
            "VALUES (:id, :slot, :name, :rank, :header_text, "
            ":restriction, :binding, :guaranteed_success, :activation, :credit) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE enchants SET slot = :slot, name = :name, rank = :rank, header_text = :header_text, "
            "restriction = :restriction, binding = :binding, guaranteed_success = :guaranteed_success, "
            "activation = :activation, credit = :credit "
            "WHERE id = :id AND (slot != :slot OR name != :name OR rank != :rank OR header_text != :header_text "
            "OR restriction IS DISTINCT FROM :restriction OR binding != :binding "
            "OR guaranteed_success != :guaranteed_success "
            "OR activation IS DISTINCT FROM :activation OR credit IS DISTINCT FROM :credit)",
            params, stats, "enchants",
        )

        for idx, eff_item in enumerate(entry["effects"], start=1):
            condition_text = eff_item.get('condition')
            effect_text = eff_item['effect']
            raw_text = f"{condition_text} {effect_text}" if condition_text else effect_text
            _, min_val, max_val = _parse_valued_effect(effect_text, effect_name_set)
            ee_params = {
                "id": eff_item['id'], "enchant_id": enchant_id,
                "effect_id": eff_item.get('effect_id'), "effect_order": idx,
                "condition_text": condition_text,
                "min_value": min_val, "max_value": max_val, "raw_text": raw_text,
            }
            _upsert(
                conn,
                "INSERT INTO enchant_effects "
                "(id, enchant_id, effect_id, effect_order, condition_text, min_value, max_value, raw_text) "
                "VALUES (:id, :enchant_id, :effect_id, :effect_order, :condition_text, :min_value, :max_value, :raw_text) "
                "ON CONFLICT (id) DO NOTHING",
                "UPDATE enchant_effects SET enchant_id = :enchant_id, effect_id = :effect_id, "
                "effect_order = :effect_order, condition_text = :condition_text, "
                "min_value = :min_value, max_value = :max_value, raw_text = :raw_text "
                "WHERE id = :id AND (enchant_id != :enchant_id OR effect_id IS DISTINCT FROM :effect_id "
                "OR effect_order != :effect_order OR condition_text IS DISTINCT FROM :condition_text "
                "OR min_value IS DISTINCT FROM :min_value OR max_value IS DISTINCT FROM :max_value "
                "OR raw_text != :raw_text)",
                ee_params, stats, "enchant_effects",
            )

    return stats.total("enchants"), stats.total("enchant_effects")


def _upsert_reforge(conn, options: list[dict], stats: ImportStats) -> int:
    for option in options:
        _upsert(
            conn,
            "INSERT INTO reforge_options (id, option_name) VALUES (:id, :option_name) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE reforge_options SET option_name = :option_name "
            "WHERE id = :id AND option_name != :option_name",
            {"id": option["id"], "option_name": option["option_name"]},
            stats, "reforge_options",
        )
    return stats.total("reforge_options")


def _upsert_game_items(conn, items: list[dict], stats: ImportStats) -> int:
    for item in items:
        _upsert(
            conn,
            "INSERT INTO game_items (id, name, type, searchable, tradable) "
            "VALUES (:id, :name, :type, :searchable, :tradable) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE game_items SET name = :name, type = :type, searchable = :searchable, tradable = :tradable "
            "WHERE id = :id AND (name != :name OR type IS DISTINCT FROM :type "
            "OR searchable != :searchable OR tradable != :tradable)",
            {
                "id": item["id"], "name": item["name"], "type": item.get("type"),
                "searchable": item.get("searchable", False), "tradable": item.get("tradable", True),
            },
            stats, "game_items",
        )
    return stats.total("game_items")


def _upsert_echostone(conn, entries: list[dict], stats: ImportStats) -> int:
    for entry in entries:
        _upsert(
            conn,
            "INSERT INTO echostone_options (id, option_name, type, max_level, min_level) "
            "VALUES (:id, :option_name, :type, :max_level, :min_level) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE echostone_options SET option_name = :option_name, type = :type, "
            "max_level = :max_level, min_level = :min_level "
            "WHERE id = :id AND (option_name != :option_name OR type != :type "
            "OR max_level IS DISTINCT FROM :max_level OR min_level IS DISTINCT FROM :min_level)",
            {
                "id": entry["id"], "option_name": entry["option_name"], "type": entry["type"],
                "max_level": entry.get("max_level"), "min_level": entry.get("min_level", 1),
            },
            stats, "echostone_options",
        )
    return stats.total("echostone_options")


def _upsert_murias_relic(conn, entries: list[dict], stats: ImportStats) -> int:
    for entry in entries:
        _upsert(
            conn,
            "INSERT INTO murias_relic_options "
            "(id, option_name, type, max_level, min_level, value_per_level, option_unit) "
            "VALUES (:id, :option_name, :type, :max_level, :min_level, :value_per_level, :option_unit) "
            "ON CONFLICT (id) DO NOTHING",
            "UPDATE murias_relic_options SET option_name = :option_name, type = :type, "
            "max_level = :max_level, min_level = :min_level, value_per_level = :value_per_level, "
            "option_unit = :option_unit "
            "WHERE id = :id AND (option_name != :option_name OR type != :type "
            "OR max_level IS DISTINCT FROM :max_level OR min_level IS DISTINCT FROM :min_level "
            "OR value_per_level IS DISTINCT FROM :value_per_level "
            "OR option_unit IS DISTINCT FROM :option_unit)",
            {
                "id": entry["id"], "option_name": entry["option_name"], "type": entry["type"],
                "max_level": entry.get("max_level"), "min_level": entry.get("min_level", 1),
                "value_per_level": entry.get("value_per_level"), "option_unit": entry.get("option_unit"),
            },
            stats, "murias_relic_options",
        )
    return stats.total("murias_relic_options")


# ── Auth seeding ──

def seed_auth(conn) -> tuple[int, int]:
    roles_created = 0
    for name in SEED_ROLES:
        exists = conn.execute(
            text("SELECT 1 FROM roles WHERE name = :n"), {"n": name}
        ).fetchone()
        if not exists:
            conn.execute(
                text("INSERT INTO roles (id, name) VALUES (:id, :n)"),
                {"id": str(uuid7()), "n": name},
            )
            roles_created += 1

    flags_created = 0
    for name in SEED_FEATURE_FLAGS:
        exists = conn.execute(
            text("SELECT 1 FROM feature_flags WHERE name = :n"), {"n": name}
        ).fetchone()
        if not exists:
            conn.execute(
                text("INSERT INTO feature_flags (id, name) VALUES (:id, :n)"),
                {"id": str(uuid7()), "n": name},
            )
            flags_created += 1

    return roles_created, flags_created


# ── Backfill ──

def backfill_listings(conn) -> int:
    result = conn.execute(
        text(
            "UPDATE listings l SET game_item_id = gi.id "
            "FROM game_items gi WHERE l.name = gi.name AND l.game_item_id IS NULL"
        )
    )
    return result.rowcount


# ── Hash tracking ──

def _compute_files_hash(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def _get_stored_hash(conn) -> str | None:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS import_metadata "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    ))
    row = conn.execute(
        text("SELECT value FROM import_metadata WHERE key = 'dictionary_hash'")
    ).fetchone()
    return row[0] if row else None


def _set_stored_hash(conn, hash_value: str) -> None:
    conn.execute(
        text(
            "INSERT INTO import_metadata (key, value) VALUES ('dictionary_hash', :h) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ),
        {"h": hash_value},
    )


# ── Main ──

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import source-of-truth YAML files into PostgreSQL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Modes:\n"
               "  (default)    Upsert: insert new, update changed, report counts.\n"
               "  --fresh      Truncate dictionary tables, then plain insert.\n"
               "  --dry-run    Run upsert but rollback. Shows what would change.",
    )
    parser.add_argument("--database-url", default="")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name", default="mabinogi")
    parser.add_argument("--db-user", default="mabinogi")
    parser.add_argument("--db-password", default="mabinogi")
    parser.add_argument("--enchant-path", default="data/source_of_truth/enchant.yaml")
    parser.add_argument("--effects-path", default="data/source_of_truth/effect.yaml")
    parser.add_argument("--reforge-path", default="data/source_of_truth/reforge.yaml")
    parser.add_argument("--item-names-path", default="data/source_of_truth/game_item.yaml")
    parser.add_argument("--echostone-path", default="data/source_of_truth/echostone.yaml")
    parser.add_argument("--murias-relic-path", default="data/source_of_truth/murias_relic.yaml")
    parser.add_argument("--backfill-listings", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore file-hash cache.")
    parser.add_argument("--fresh", action="store_true", help="Truncate dictionary tables before import.")
    parser.add_argument("--dry-run", action="store_true", help="Rollback after import (preview only).")
    args = parser.parse_args()

    enchant_path = Path(args.enchant_path)
    effects_path = Path(args.effects_path)
    reforge_path = Path(args.reforge_path)
    item_names_path = Path(args.item_names_path)
    echostone_path = Path(args.echostone_path)
    murias_relic_path = Path(args.murias_relic_path)

    for p, label in [(enchant_path, "Enchant"), (effects_path, "Effects"), (reforge_path, "Reforge")]:
        if not p.exists():
            raise FileNotFoundError(f"{label} file not found: {p}")

    db_url = _db_url_from_args(args)
    engine = create_engine(db_url, pool_pre_ping=True)

    # Hash check (skip unless --force or --fresh)
    file_hash = _compute_files_hash(
        enchant_path, effects_path, reforge_path, item_names_path,
        echostone_path, murias_relic_path,
    )
    if not args.fresh:
        with engine.begin() as conn:
            stored_hash = _get_stored_hash(conn)
        if stored_hash == file_hash and not args.force and not args.dry_run:
            print("Dictionary files unchanged — skipping import.")
            return

    # Parse all files
    effects_data = parse_effects_file(effects_path)
    enchant_entries = parse_enchant(enchant_path)
    reforge_options = parse_reforge(reforge_path)

    game_items = []
    if item_names_path.exists():
        game_items = parse_game_items(item_names_path)
    else:
        print(f"Warning: {item_names_path} not found — skipping game_items")

    echostone_entries = []
    if echostone_path.exists():
        echostone_entries = parse_echostone(echostone_path)

    murias_relic_entries = []
    if murias_relic_path.exists():
        murias_relic_entries = parse_murias_relic(murias_relic_path)

    if args.dry_run:
        print("[DRY RUN] Changes will be rolled back.\n")

    conn = engine.connect()
    txn = conn.begin()
    try:
        # Seed auth
        roles_created, flags_created = seed_auth(conn)
        if roles_created or flags_created:
            print(f"  auth: {roles_created} roles, {flags_created} feature_flags seeded")

        if args.fresh:
            # Fresh mode: truncate + plain insert
            for table in DICT_TABLES:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print("  Truncated dictionary tables.")

            effect_name_to_id = _insert_effects(conn, effects_data)
            enchant_count, link_count = _insert_enchants(conn, enchant_entries, effect_name_to_id)
            reforge_count = _insert_reforge(conn, reforge_options)
            game_items_count = _insert_game_items(conn, game_items) if game_items else 0
            echostone_count = _insert_echostone(conn, echostone_entries) if echostone_entries else 0
            murias_relic_count = _insert_murias_relic(conn, murias_relic_entries) if murias_relic_entries else 0

            print(
                f"Imported: game_items={game_items_count}, effects={len(effect_name_to_id)}, "
                f"enchants={enchant_count}, enchant_effects={link_count}, "
                f"reforge_options={reforge_count}, echostone={echostone_count}, "
                f"murias_relic={murias_relic_count}"
            )
        else:
            # Upsert mode: insert new, update changed, report
            stats = ImportStats()

            effect_name_to_id = _upsert_effects(conn, effects_data, stats)
            _upsert_enchants(conn, enchant_entries, effect_name_to_id, stats)
            _upsert_reforge(conn, reforge_options, stats)
            if game_items:
                _upsert_game_items(conn, game_items, stats)
            if echostone_entries:
                _upsert_echostone(conn, echostone_entries, stats)
            if murias_relic_entries:
                _upsert_murias_relic(conn, murias_relic_entries, stats)

            stats.print_report()
            print(f"Total: {stats.summary_line()}")

        if args.backfill_listings:
            count = backfill_listings(conn)
            print(f"Backfilled {count} listing(s) with game_item_id")

        if args.dry_run:
            txn.rollback()
            print("\n[DRY RUN] Rolled back — no changes committed.")
        else:
            _set_stored_hash(conn, file_hash)
            txn.commit()
    except Exception:
        txn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
