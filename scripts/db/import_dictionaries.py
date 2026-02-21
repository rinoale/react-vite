#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text


HEADER_RE = re.compile(r"^\[(접두|접미)\]\s+(.+?)\s+\(랭크\s+([^)]+)\)$")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
VALUE_DIR_RE = re.compile(
    r"^(?P<prefix>.*)\s(?P<value>[+-]?\d+(?:\.\d+)?)\s*%?\s*(?P<direction>증가|감소)\s*$"
)
RANK_LETTER_TO_INT = {
    "A": 10,
    "B": 11,
    "C": 12,
    "D": 13,
    "E": 14,
    "F": 15,
}


def _db_url_from_args(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url
    return (
        f"postgresql+psycopg2://{args.db_user}:{args.db_password}"
        f"@{args.db_host}:{args.db_port}/{args.db_name}"
    )


def parse_enchant(path: Path) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue

        m = HEADER_RE.match(line)
        if m:
            if current is not None:
                entries.append(current)
            slot_kr, name, rank = m.groups()
            slot = 0 if slot_kr == "접두" else 1
            rank = rank.strip()
            rank_int = RANK_LETTER_TO_INT.get(rank.upper())
            if rank_int is None:
                rank_int = int(rank)
            current = {
                "slot": slot,
                "name": name.strip(),
                "rank": rank_int,
                "header_text": line,
                "effects": [],
            }
            continue

        if current is None:
            continue
        current["effects"].append(line)

    if current is not None:
        entries.append(current)

    return entries


def _normalize_effect_text(effect_text: str) -> str:
    normalized = NUMBER_RE.sub("N", effect_text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _split_condition(effect_text: str) -> tuple[str | None, str]:
    """Split '<condition>때 <effect>' into (condition_text, effect_text).

    If no condition exists, returns (None, original_text).
    """
    if "때" not in effect_text:
        return None, effect_text.strip()

    left, right = effect_text.split("때", 1)
    condition = f"{left.strip()}때"
    effect = right.strip().lstrip(",").strip()
    return condition, effect if effect else effect_text.strip()


def _extract_effect_value_and_direction(effect_text: str) -> tuple[float | None, int | None]:
    """Extract numeric value and increase/decrease direction from an effect text.

    Returns:
      (value, direction)
      direction: 0=increase, 1=decrease
    """
    m = VALUE_DIR_RE.match(effect_text.strip())
    if not m:
        return None, None

    value = float(m.group("value"))
    direction = 0 if m.group("direction") == "증가" else 1
    return value, direction


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


def parse_valuable_effects(path: Path) -> list[str]:
    if not path.exists():
        return []
    seen = set()
    effects = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        effects.append(line)
    return effects


def chunked(items: Iterable, size: int) -> Iterable[list]:
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def import_enchant(conn, enchant_entries: list[dict]) -> tuple[int, int, int]:
    entry_count = 0
    link_count = 0

    for entry in enchant_entries:
        row = conn.execute(
            text(
                """
                INSERT INTO enchant_entries (slot, name, rank, header_text)
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

        conn.execute(
            text("DELETE FROM enchant_entry_effect_links WHERE enchant_entry_id = :entry_id"),
            {"entry_id": enchant_id},
        )

        for idx, raw_effect_text in enumerate(entry["effects"], start=1):
            condition_text, effect_text = _split_condition(raw_effect_text)
            normalized_text = _normalize_effect_text(effect_text)
            effect_value, effect_direction = _extract_effect_value_and_direction(effect_text)

            effect_row = conn.execute(
                text(
                    """
                    INSERT INTO enchant_effects (normalized_text)
                    VALUES (:normalized_text)
                    ON CONFLICT (normalized_text)
                    DO UPDATE SET normalized_text = EXCLUDED.normalized_text
                    RETURNING id
                    """
                ),
                {"normalized_text": normalized_text},
            ).fetchone()
            enchant_effect_id = effect_row[0]

            conn.execute(
                text(
                    """
                    INSERT INTO enchant_entry_effect_links
                    (
                        enchant_entry_id,
                        enchant_effect_id,
                        effect_order,
                        condition_text,
                        effect_value,
                        effect_direction,
                        raw_text
                    )
                    VALUES
                    (
                        :enchant_entry_id,
                        :enchant_effect_id,
                        :effect_order,
                        :condition_text,
                        :effect_value,
                        :effect_direction,
                        :raw_text
                    )
                    """
                ),
                {
                    "enchant_entry_id": enchant_id,
                    "enchant_effect_id": enchant_effect_id,
                    "effect_order": idx,
                    "condition_text": condition_text,
                    "effect_value": effect_value,
                    "effect_direction": effect_direction,
                    "raw_text": raw_effect_text,
                },
            )
            link_count += 1

    unique_effect_count = conn.execute(
        text("SELECT COUNT(*) FROM enchant_effects")
    ).scalar_one()
    return entry_count, link_count, int(unique_effect_count)


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


def import_valuable_effects(conn, effects: list[str]) -> int:
    count = 0
    for effect in effects:
        conn.execute(
            text(
                """
                INSERT INTO enchant_effects (normalized_text)
                VALUES (:normalized_text)
                ON CONFLICT (normalized_text)
                DO UPDATE SET normalized_text = EXCLUDED.normalized_text
                """
            ),
            {"normalized_text": effect},
        )
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import enchant/reforge dictionary files into PostgreSQL."
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
        default="data/dictionary/enchant.txt",
        help="Path to enchant dictionary file.",
    )
    parser.add_argument(
        "--reforge-path",
        default="data/dictionary/reforge.txt",
        help="Path to reforge dictionary file.",
    )
    parser.add_argument(
        "--valuable-effects-path",
        default="tmp/enchant_effects_split/valuable_effects.txt",
        help="Optional path to preload normalized valuable effects into enchant_effects.",
    )
    args = parser.parse_args()

    enchant_path = Path(args.enchant_path)
    reforge_path = Path(args.reforge_path)
    if not enchant_path.exists():
        raise FileNotFoundError(f"Enchant file not found: {enchant_path}")
    if not reforge_path.exists():
        raise FileNotFoundError(f"Reforge file not found: {reforge_path}")

    enchant_entries = parse_enchant(enchant_path)
    reforge_options = parse_reforge(reforge_path)
    valuable_effects = parse_valuable_effects(Path(args.valuable_effects_path))
    db_url = _db_url_from_args(args)

    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        valuable_count = import_valuable_effects(conn, valuable_effects) if valuable_effects else 0
        enchant_count, link_count, unique_effect_count = import_enchant(conn, enchant_entries)
        reforge_count = import_reforge(conn, reforge_options)

    print(
        "Imported dictionaries:"
        f" valuable_effects_loaded={valuable_count},"
        f" enchant_entries={enchant_count},"
        f" enchant_effect_links={link_count},"
        f" enchant_effects_unique={unique_effect_count},"
        f" reforge_options={reforge_count}"
    )


if __name__ == "__main__":
    main()
