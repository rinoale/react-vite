#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Iterable

import yaml
from sqlalchemy import create_engine, text


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
        entries.append({
            "slot": slot,
            "name": item["name"],
            "rank": _rank_to_int(rank_str),
            "header_text": header_text,
            "effects": item.get("effects", []),
        })

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
    # effects.txt names may have " (%)" suffix for percentage effects.
    # raw_name from yaml won't have that suffix.
    if raw_name in effect_name_set:
        return raw_name, sign * min_val, sign * max_val

    # Try with (%) suffix for percentage effects
    pct_name = f"{raw_name} (%)"
    if pct_name in effect_name_set:
        return pct_name, sign * min_val, sign * max_val

    return None, None, None


def parse_effects_file(path: Path) -> list[dict]:
    """Parse effects.txt into list of {name, is_pct}."""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        is_pct = line.endswith("(%)")
        results.append({"name": line, "is_pct": is_pct})
    return results


def parse_reforge(path: Path) -> list[str]:
    seen = set()
    options: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        options.append(line)
    return options


def parse_game_items(path: Path) -> list[str]:
    """Parse item_name.txt into deduplicated list of item names."""
    seen = set()
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        names.append(line)
    return names


def chunked(items: Iterable, size: int) -> Iterable[list]:
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def import_effects(conn, effects: list[dict]) -> dict[str, int]:
    """Import effects.txt rows into effects table. Returns {name: id} map."""
    name_to_id = {}
    for eff in effects:
        row = conn.execute(
            text(
                """
                INSERT INTO effects (name, is_pct)
                VALUES (:name, :is_pct)
                ON CONFLICT (name)
                DO UPDATE SET is_pct = EXCLUDED.is_pct
                RETURNING id
                """
            ),
            {"name": eff["name"], "is_pct": eff["is_pct"]},
        ).fetchone()
        name_to_id[eff["name"]] = row[0]
    return name_to_id


def import_enchant(
    conn, enchant_entries: list[dict], effect_name_to_id: dict[str, int]
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
        row = conn.execute(
            text(
                """
                INSERT INTO enchants (slot, name, rank, header_text)
                VALUES (:slot, :name, :rank, :header_text)
                ON CONFLICT (header_text)
                DO UPDATE SET
                    slot = EXCLUDED.slot,
                    name = EXCLUDED.name,
                    rank = EXCLUDED.rank
                RETURNING id
                """
            ),
            {
                "slot": entry["slot"],
                "name": entry["name"],
                "rank": entry["rank"],
                "header_text": entry["header_text"],
            },
        ).fetchone()

        enchant_id = row[0]
        entry_count += 1

        # Clear old links for upsert
        conn.execute(
            text("DELETE FROM enchant_effects WHERE enchant_id = :eid"),
            {"eid": enchant_id},
        )

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

            conn.execute(
                text(
                    """
                    INSERT INTO enchant_effects
                    (enchant_id, effect_id, effect_order, condition_text,
                     min_value, max_value, raw_text)
                    VALUES
                    (:enchant_id, :effect_id, :effect_order, :condition_text,
                     :min_value, :max_value, :raw_text)
                    """
                ),
                {
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


def import_reforge(conn, reforge_options: list[str]) -> int:
    count = 0
    for batch in chunked(reforge_options, 200):
        for option in batch:
            conn.execute(
                text(
                    """
                    INSERT INTO reforge_options (option_name)
                    VALUES (:option_name)
                    ON CONFLICT (option_name)
                    DO UPDATE SET option_name = EXCLUDED.option_name
                    """
                ),
                {"option_name": option},
            )
            count += 1
    return count


def import_game_items(conn, names: list[str]) -> int:
    """Import game item names into game_items table. Returns count."""
    count = 0
    for batch in chunked(names, 500):
        for name in batch:
            conn.execute(
                text(
                    """
                    INSERT INTO game_items (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                {"name": name},
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
        default="data/source_of_truth/effects.txt",
        help="Path to effects list file.",
    )
    parser.add_argument(
        "--reforge-path",
        default="data/dictionary/reforge.txt",
        help="Path to reforge dictionary file.",
    )
    parser.add_argument(
        "--item-names-path",
        default="data/dictionary/item_name.txt",
        help="Path to game item names dictionary file.",
    )
    parser.add_argument(
        "--backfill-listings",
        action="store_true",
        help="Backfill game_item_id on existing listings where name matches.",
    )
    args = parser.parse_args()

    enchant_path = Path(args.enchant_path)
    effects_path = Path(args.effects_path)
    reforge_path = Path(args.reforge_path)
    item_names_path = Path(args.item_names_path)

    if not enchant_path.exists():
        raise FileNotFoundError(f"Enchant file not found: {enchant_path}")
    if not effects_path.exists():
        raise FileNotFoundError(f"Effects file not found: {effects_path}")
    if not reforge_path.exists():
        raise FileNotFoundError(f"Reforge file not found: {reforge_path}")

    effects_data = parse_effects_file(effects_path)
    enchant_entries = parse_enchant(enchant_path)
    reforge_options = parse_reforge(reforge_path)

    # Game items are optional (file may not exist yet)
    game_item_names = []
    if item_names_path.exists():
        game_item_names = parse_game_items(item_names_path)
    else:
        print(f"Warning: Item names file not found: {item_names_path} — skipping game_items import")

    db_url = _db_url_from_args(args)
    engine = create_engine(db_url, pool_pre_ping=True)

    with engine.begin() as conn:
        # Import game items first (no dependencies)
        game_items_count = 0
        if game_item_names:
            game_items_count = import_game_items(conn, game_item_names)

        effect_name_to_id = import_effects(conn, effects_data)
        enchant_count, link_count = import_enchant(
            conn, enchant_entries, effect_name_to_id
        )
        reforge_count = import_reforge(conn, reforge_options)

        backfill_count = 0
        if args.backfill_listings:
            backfill_count = backfill_listings(conn)

    print(
        "Imported dictionaries:"
        f" game_items={game_items_count},"
        f" effects={len(effect_name_to_id)},"
        f" enchants={enchant_count},"
        f" enchant_effects={link_count},"
        f" reforge_options={reforge_count}"
    )
    if args.backfill_listings:
        print(f"Backfilled {backfill_count} listing(s) with game_item_id")


if __name__ == "__main__":
    main()
