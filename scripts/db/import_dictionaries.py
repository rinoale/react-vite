#!/usr/bin/env python3
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
# Also handles percentage effects like "수리비 200%  증가"
# and "아르카나 스킬 보너스 대미지 1% 증가"
VALUED_EFFECT_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<min>\d+(?:\.\d+)?)"
    r"(?:\s*~\s*(?P<max>\d+(?:\.\d+)?))?"
    r"\s*%?\s+"
    r"(?P<dir>증가|감소)\s*$"
)

# Condition: everything before "때" (inclusive), effect: everything after
CONDITION_RE = re.compile(r"^(?P<cond>.+?때)\s*,?\s*(?P<effect>.+)$")


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


def _split_condition(effect_text: str) -> tuple[str | None, str]:
    """Split '<condition>때 <effect>' into (condition_text, effect_text).

    Returns (None, original_text) if no condition.
    """
    m = CONDITION_RE.match(effect_text)
    if m and m.group("effect"):
        return m.group("cond"), m.group("effect")
    return None, effect_text


def _parse_valued_effect(
    effect_text: str, effect_name_set: set[str]
) -> tuple[int | None, float | None, float | None]:
    """Try to match effect_text against known effect names and extract values.

    Returns (effect_id_placeholder_name_index, min_value, max_value).
    We return the effect name for lookup; caller resolves to effect_id.

    Actually returns: (effect_name or None, min_val, max_val)
    """
    m = VALUED_EFFECT_RE.match(effect_text.strip())
    if not m:
        return None, None, None

    raw_name = m.group("name").strip()
    min_val = float(m.group("min"))
    max_val = float(m.group("max")) if m.group("max") else min_val
    sign = 1 if m.group("dir") == "증가" else -1

    # Match raw_name to a known effect name.
    # effects may have " (%)" suffix for percentage effects.
    # raw_name from yaml won't have that suffix.
    if raw_name in effect_name_set:
        return raw_name, sign * min_val, sign * max_val

    # Try with (%) suffix for percentage effects
    pct_name = f"{raw_name} (%)"
    if pct_name in effect_name_set:
        return pct_name, sign * min_val, sign * max_val

    return None, None, None


def parse_effects_file(path: Path) -> list[dict]:
    """Parse effect.yaml into list of {id, name, is_pct}."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return [{"id": entry["id"], "name": entry["name"], "is_pct": entry["is_pct"]} for entry in data]


def parse_reforge(path: Path) -> list[dict]:
    """Parse reforge.yaml (dict: {reforgeName: [{option_name, option_id, ...}]}).

    Deduplicates by option_id. Returns list of {id, option_name} dicts.
    """
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
    """Parse game_item.yaml into list of {id, name, type, searchable, tradable}."""
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


def chunked(items: Iterable, size: int) -> Iterable[list]:
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def import_effects(conn, effects: list[dict]) -> dict[str, str]:
    """Import effect.yaml rows into effects table. Returns {name: uuid_id} map."""
    name_to_id: dict[str, str] = {}
    for eff in effects:
        conn.execute(
            text(
                """
                INSERT INTO effects (id, name, is_pct)
                VALUES (:id, :name, :is_pct)
                """
            ),
            {"id": eff["id"], "name": eff["name"], "is_pct": eff["is_pct"]},
        )
        name_to_id[eff["name"]] = eff["id"]
    return name_to_id


def import_enchant(
    conn, enchant_entries: list[dict], effect_name_to_id: dict[str, str]
) -> tuple[int, int]:
    """Import enchants and enchant_effects. Returns (enchant_count, link_count)."""
    effect_name_set = set(effect_name_to_id.keys())
    # Build a lookup set without " (%)" suffix for matching
    bare_to_full: dict[str, str] = {}
    for name in effect_name_set:
        if name.endswith("(%)"):
            bare = name[: -len("(%)")].strip()
            bare_to_full[bare] = name
    # Add bare names that don't have (%) variant
    for name in effect_name_set:
        if not name.endswith("(%)"):
            bare_to_full.setdefault(name, name)

    entry_count = 0
    link_count = 0

    for entry in enchant_entries:
        enchant_id = entry["id"]
        conn.execute(
            text(
                """
                INSERT INTO enchants (id, slot, name, rank, header_text,
                                      restriction, binding, guaranteed_success,
                                      activation, credit)
                VALUES (:id, :slot, :name, :rank, :header_text,
                        :restriction, :binding, :guaranteed_success,
                        :activation, :credit)
                """
            ),
            {
                "id": enchant_id,
                "slot": entry["slot"],
                "name": entry["name"],
                "rank": entry["rank"],
                "header_text": entry["header_text"],
                "restriction": entry.get("restriction"),
                "binding": entry.get("binding", False),
                "guaranteed_success": entry.get("guaranteed_success", False),
                "activation": entry.get("activation"),
                "credit": entry.get("credit"),
            },
        )

        entry_count += 1

        for idx, eff_item in enumerate(entry["effects"], start=1):
            if isinstance(eff_item, dict):
                condition_text = eff_item.get('condition')
                effect_text = eff_item['effect']
                raw_text = f"{condition_text} {effect_text}" if condition_text else effect_text
            else:
                raw_text = eff_item
                condition_text, effect_text = _split_condition(raw_text)

            # Try to parse as a valued effect
            effect_name, min_val, max_val = _parse_valued_effect(
                effect_text, effect_name_set
            )
            effect_id = effect_name_to_id.get(effect_name) if effect_name else None

            ee_id = str(uuid7())
            conn.execute(
                text(
                    """
                    INSERT INTO enchant_effects
                    (id, enchant_id, effect_id, effect_order, condition_text,
                     min_value, max_value, raw_text)
                    VALUES
                    (:id, :enchant_id, :effect_id, :effect_order, :condition_text,
                     :min_value, :max_value, :raw_text)
                    """
                ),
                {
                    "id": ee_id,
                    "enchant_id": enchant_id,
                    "effect_id": effect_id,
                    "effect_order": idx,
                    "condition_text": condition_text,
                    "min_value": min_val,
                    "max_value": max_val,
                    "raw_text": raw_text,
                },
            )
            link_count += 1


    return entry_count, link_count


def import_reforge(conn, reforge_options: list[dict]) -> int:
    count = 0
    for batch in chunked(reforge_options, 200):
        for option in batch:
            conn.execute(
                text(
                    """
                    INSERT INTO reforge_options (id, option_name)
                    VALUES (:id, :option_name)
                    """
                ),
                {"id": option["id"], "option_name": option["option_name"]},
            )
            count += 1
    return count


def import_game_items(conn, items: list[dict]) -> int:
    """Import game items from game_item.yaml into game_items table. Returns count."""
    count = 0
    for batch in chunked(items, 500):
        for item in batch:
            conn.execute(
                text(
                    """
                    INSERT INTO game_items (id, name, type, searchable, tradable)
                    VALUES (:id, :name, :type, :searchable, :tradable)
                    """
                ),
                {
                    "id": item["id"],
                    "name": item["name"],
                    "type": item.get("type"),
                    "searchable": item.get("searchable", False),
                    "tradable": item.get("tradable", True),
                },
            )
            count += 1
    return count


def parse_echostone(path: Path) -> list[dict]:
    """Parse echostone.yaml into list of {id, option_name, type, max_level, min_level}."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def parse_murias_relic(path: Path) -> list[dict]:
    """Parse murias_relic.yaml into list of {id, option_name, type, max_level, min_level, value_per_level, option_unit}."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def import_echostone(conn, entries: list[dict]) -> int:
    count = 0
    for entry in entries:
        conn.execute(
            text(
                """
                INSERT INTO echostone_options (id, option_name, type, max_level, min_level)
                VALUES (:id, :option_name, :type, :max_level, :min_level)
                """
            ),
            {
                "id": entry["id"],
                "option_name": entry["option_name"],
                "type": entry["type"],
                "max_level": entry.get("max_level"),
                "min_level": entry.get("min_level", 1),
            },
        )
        count += 1
    return count


def import_murias_relic(conn, entries: list[dict]) -> int:
    count = 0
    for entry in entries:
        conn.execute(
            text(
                """
                INSERT INTO murias_relic_options
                    (id, option_name, type, max_level, min_level, value_per_level, option_unit)
                VALUES
                    (:id, :option_name, :type, :max_level, :min_level, :value_per_level, :option_unit)
                """
            ),
            {
                "id": entry["id"],
                "option_name": entry["option_name"],
                "type": entry["type"],
                "max_level": entry.get("max_level"),
                "min_level": entry.get("min_level", 1),
                "value_per_level": entry.get("value_per_level"),
                "option_unit": entry.get("option_unit"),
            },
        )
        count += 1
    return count


def backfill_listings(conn) -> int:
    """Set game_item_id on listings where name matches a game_item exactly."""
    result = conn.execute(
        text(
            """
            UPDATE listings l
            SET game_item_id = gi.id
            FROM game_items gi
            WHERE l.name = gi.name
              AND l.game_item_id IS NULL
            """
        )
    )
    return result.rowcount


def _compute_files_hash(*paths: Path) -> str:
    """SHA-256 hash of all input files combined."""
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import enchant/reforge/game-item dictionary files into PostgreSQL."
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="SQLAlchemy DB URL. Overrides individual --db-* args.",
    )
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name", default="mabinogi")
    parser.add_argument("--db-user", default="mabinogi")
    parser.add_argument("--db-password", default="mabinogi")
    parser.add_argument(
        "--enchant-path",
        default="data/source_of_truth/enchant.yaml",
        help="Path to enchant dictionary file (YAML).",
    )
    parser.add_argument(
        "--effects-path",
        default="data/source_of_truth/effect.yaml",
        help="Path to effects file (YAML).",
    )
    parser.add_argument(
        "--reforge-path",
        default="data/source_of_truth/reforge.yaml",
        help="Path to reforge dictionary file (YAML).",
    )
    parser.add_argument(
        "--item-names-path",
        default="data/source_of_truth/game_item.yaml",
        help="Path to game items file (YAML).",
    )
    parser.add_argument(
        "--echostone-path",
        default="data/source_of_truth/echostone.yaml",
        help="Path to echostone options file (YAML).",
    )
    parser.add_argument(
        "--murias-relic-path",
        default="data/source_of_truth/murias_relic.yaml",
        help="Path to murias relic options file (YAML).",
    )
    parser.add_argument(
        "--backfill-listings",
        action="store_true",
        help="Backfill game_item_id on existing listings where name matches.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force import even if dictionary files haven't changed.",
    )
    args = parser.parse_args()

    enchant_path = Path(args.enchant_path)
    effects_path = Path(args.effects_path)
    reforge_path = Path(args.reforge_path)
    item_names_path = Path(args.item_names_path)
    echostone_path = Path(args.echostone_path)
    murias_relic_path = Path(args.murias_relic_path)

    if not enchant_path.exists():
        raise FileNotFoundError(f"Enchant file not found: {enchant_path}")
    if not effects_path.exists():
        raise FileNotFoundError(f"Effects file not found: {effects_path}")
    if not reforge_path.exists():
        raise FileNotFoundError(f"Reforge file not found: {reforge_path}")

    db_url = _db_url_from_args(args)
    engine = create_engine(db_url, pool_pre_ping=True)

    # Check if dictionary files changed since last import
    file_hash = _compute_files_hash(
        enchant_path, effects_path, reforge_path, item_names_path,
        echostone_path, murias_relic_path,
    )
    with engine.begin() as conn:
        stored_hash = _get_stored_hash(conn)

    if stored_hash == file_hash and not args.force:
        print("Dictionary files unchanged — skipping import.")
        return

    effects_data = parse_effects_file(effects_path)
    enchant_entries = parse_enchant(enchant_path)
    reforge_options = parse_reforge(reforge_path)

    # Game items are optional (file may not exist yet)
    game_items = []
    if item_names_path.exists():
        game_items = parse_game_items(item_names_path)
    else:
        print(f"Warning: Game items file not found: {item_names_path} — skipping game_items import")

    # Echostone and murias relic are optional
    echostone_entries = []
    if echostone_path.exists():
        echostone_entries = parse_echostone(echostone_path)
    else:
        print(f"Warning: Echostone file not found: {echostone_path} — skipping")

    murias_relic_entries = []
    if murias_relic_path.exists():
        murias_relic_entries = parse_murias_relic(murias_relic_path)
    else:
        print(f"Warning: Murias relic file not found: {murias_relic_path} — skipping")

    with engine.begin() as conn:
        # Import game items first (no dependencies)
        game_items_count = 0
        if game_items:
            game_items_count = import_game_items(conn, game_items)

        effect_name_to_id = import_effects(conn, effects_data)
        enchant_count, link_count = import_enchant(
            conn, enchant_entries, effect_name_to_id
        )
        reforge_count = import_reforge(conn, reforge_options)

        echostone_count = 0
        if echostone_entries:
            echostone_count = import_echostone(conn, echostone_entries)

        murias_relic_count = 0
        if murias_relic_entries:
            murias_relic_count = import_murias_relic(conn, murias_relic_entries)

        backfill_count = 0
        if args.backfill_listings:
            backfill_count = backfill_listings(conn)

        _set_stored_hash(conn, file_hash)

    print(
        "Imported dictionaries:"
        f" game_items={game_items_count},"
        f" effects={len(effect_name_to_id)},"
        f" enchants={enchant_count},"
        f" enchant_effects={link_count},"
        f" reforge_options={reforge_count},"
        f" echostone={echostone_count},"
        f" murias_relic={murias_relic_count}"
    )
    if args.backfill_listings:
        print(f"Backfilled {backfill_count} listing(s) with game_item_id")


if __name__ == "__main__":
    main()
