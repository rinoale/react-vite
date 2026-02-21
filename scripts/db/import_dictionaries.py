#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text


HEADER_RE = re.compile(r"^\[(접두|접미)\]\s+(.+?)\s+\(랭크\s+([^)]+)\)$")
NUMBER_RE = re.compile(r"^(.+?)\s+([+-]?\d+)(?:\s|$)")


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
            current = {
                "slot": "prefix" if slot_kr == "접두" else "suffix",
                "name": name.strip(),
                "rank": rank.strip(),
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


def _extract_option_fields(effect_text: str) -> tuple[str | None, int | None]:
    m = NUMBER_RE.match(effect_text)
    if not m:
        return None, None
    option_name, option_level = m.groups()
    return option_name.strip(), int(option_level)


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


def chunked(items: Iterable, size: int) -> Iterable[list]:
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def import_enchant(conn, enchant_entries: list[dict], source_file: str) -> tuple[int, int]:
    entry_count = 0
    effect_count = 0

    for entry in enchant_entries:
        row = conn.execute(
            text(
                """
                INSERT INTO enchant_entries (slot, name, rank, header_text, source_file)
                VALUES (:slot, :name, :rank, :header_text, :source_file)
                ON CONFLICT (header_text)
                DO UPDATE SET
                    slot = EXCLUDED.slot,
                    name = EXCLUDED.name,
                    rank = EXCLUDED.rank,
                    source_file = EXCLUDED.source_file
                RETURNING id
                """
            ),
            {
                "slot": entry["slot"],
                "name": entry["name"],
                "rank": entry["rank"],
                "header_text": entry["header_text"],
                "source_file": source_file,
            },
        ).fetchone()

        enchant_id = row[0]
        entry_count += 1

        conn.execute(
            text("DELETE FROM enchant_effects WHERE enchant_entry_id = :entry_id"),
            {"entry_id": enchant_id},
        )

        for idx, effect_text in enumerate(entry["effects"], start=1):
            option_name, option_level = _extract_option_fields(effect_text)
            conn.execute(
                text(
                    """
                    INSERT INTO enchant_effects
                    (enchant_entry_id, effect_order, text, option_name, option_level)
                    VALUES (:entry_id, :effect_order, :text, :option_name, :option_level)
                    """
                ),
                {
                    "entry_id": enchant_id,
                    "effect_order": idx,
                    "text": effect_text,
                    "option_name": option_name,
                    "option_level": option_level,
                },
            )
            effect_count += 1

    return entry_count, effect_count


def import_reforge(conn, reforge_options: list[str], source_file: str) -> int:
    count = 0
    for batch in chunked(reforge_options, 200):
        for option in batch:
            conn.execute(
                text(
                    """
                    INSERT INTO reforge_options (option_name, source_file)
                    VALUES (:option_name, :source_file)
                    ON CONFLICT (option_name)
                    DO UPDATE SET source_file = EXCLUDED.source_file
                    """
                ),
                {"option_name": option, "source_file": source_file},
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
    args = parser.parse_args()

    enchant_path = Path(args.enchant_path)
    reforge_path = Path(args.reforge_path)
    if not enchant_path.exists():
        raise FileNotFoundError(f"Enchant file not found: {enchant_path}")
    if not reforge_path.exists():
        raise FileNotFoundError(f"Reforge file not found: {reforge_path}")

    enchant_entries = parse_enchant(enchant_path)
    reforge_options = parse_reforge(reforge_path)
    db_url = _db_url_from_args(args)

    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        enchant_count, effect_count = import_enchant(
            conn, enchant_entries, str(enchant_path)
        )
        reforge_count = import_reforge(conn, reforge_options, str(reforge_path))

    print(
        "Imported dictionaries:"
        f" enchant_entries={enchant_count},"
        f" enchant_effects={effect_count},"
        f" reforge_options={reforge_count}"
    )


if __name__ == "__main__":
    main()
