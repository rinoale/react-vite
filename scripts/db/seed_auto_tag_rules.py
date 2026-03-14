#!/usr/bin/env python3
"""Seed auto_tag_rules table with default rules.

Upsert by name — inserts new rules, skips existing ones.
Use --force to overwrite existing rules with seed values.
"""
import argparse
import json

from sqlalchemy import create_engine, text
from uuid_utils import uuid7


SEED_RULES = [
    {
        "name": "full_piercing",
        "description": "Tag when piercing level equals max roll",
        "rule_type": "condition",
        "priority": 0,
        "config": {
            "conditions": [
                {"table": "enchant_effects", "column": "option_name", "op": "==", "value": "피어싱 레벨", "refer": "", "logic": "AND"},
                {"table": "enchant_effects", "column": "rolled_value", "op": "==", "value": {"table": "enchant_effects", "column": "max_level"}, "refer": "", "logic": "AND"},
            ],
            "tag_template": "풀피어싱",
        },
    },
    {
        "name": "erg_max",
        "description": "Tag when erg grade is S and level is 50",
        "rule_type": "condition",
        "priority": 0,
        "config": {
            "conditions": [
                {"table": "listing", "column": "erg_grade", "op": "==", "value": "S", "refer": "erg_grade", "logic": "AND"},
                {"table": "listing", "column": "erg_level", "op": "==", "value": 50, "refer": "erg_level", "logic": "AND"},
            ],
            "tag_template": "{erg_grade}르그{erg_level}",
        },
    },
    {
        "name": "special_upgrade",
        "description": "Tag when special upgrade level >= 7",
        "rule_type": "condition",
        "priority": 0,
        "config": {
            "conditions": [
                {"table": "listing", "column": "special_upgrade_level", "op": ">=", "value": 7, "refer": "level", "logic": "AND"},
                {"table": "listing", "column": "special_upgrade_type", "op": "!=", "value": None, "refer": "type", "logic": "AND"},
            ],
            "tag_template": "{type}{level}",
        },
    },
    {
        "name": "prefix_enchant",
        "description": "Tag with prefix enchant name",
        "rule_type": "condition",
        "priority": 0,
        "config": {
            "conditions": [
                {"table": "prefix_enchant", "column": "name", "op": "!=", "value": None, "refer": "name", "logic": "AND"},
            ],
            "tag_template": "{name}",
        },
    },
    {
        "name": "suffix_enchant",
        "description": "Tag with suffix enchant name",
        "rule_type": "condition",
        "priority": 0,
        "config": {
            "conditions": [
                {"table": "suffix_enchant", "column": "name", "op": "!=", "value": None, "refer": "name", "logic": "AND"},
            ],
            "tag_template": "{name}",
        },
    },
]


def _db_url_from_args(args):
    if args.database_url:
        return args.database_url
    return (
        f"postgresql+psycopg2://{args.db_user}:{args.db_password}"
        f"@{args.db_host}:{args.db_port}/{args.db_name}"
    )


def seed_rules(conn, force=False):
    inserted = 0
    updated = 0
    skipped = 0

    for rule in SEED_RULES:
        params = {
            "id": str(uuid7()),
            "name": rule["name"],
            "description": rule["description"],
            "rule_type": rule["rule_type"],
            "priority": rule["priority"],
            "config": json.dumps(rule["config"]),
        }

        result = conn.execute(
            text(
                "INSERT INTO auto_tag_rules (id, name, description, rule_type, priority, config) "
                "VALUES (:id, :name, :description, :rule_type, :priority, CAST(:config AS jsonb)) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            params,
        )

        if result.rowcount > 0:
            inserted += 1
            print(f"  + {rule['name']}")
        elif force:
            conn.execute(
                text(
                    "UPDATE auto_tag_rules SET description = :description, rule_type = :rule_type, "
                    "priority = :priority, config = CAST(:config AS jsonb) "
                    "WHERE name = :name"
                ),
                params,
            )
            updated += 1
            print(f"  ~ {rule['name']} (updated)")
        else:
            skipped += 1
            print(f"  . {rule['name']} (exists)")

    return inserted, updated, skipped


def main():
    parser = argparse.ArgumentParser(description="Seed auto_tag_rules table.")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name", default="mabinogi")
    parser.add_argument("--db-user", default="mabinogi")
    parser.add_argument("--db-password", default="mabinogi")
    parser.add_argument("--force", action="store_true", help="Overwrite existing rules with seed values.")
    parser.add_argument("--dry-run", action="store_true", help="Rollback after seed (preview only).")
    args = parser.parse_args()

    engine = create_engine(_db_url_from_args(args), pool_pre_ping=True)

    if args.dry_run:
        print("[DRY RUN] Changes will be rolled back.\n")

    conn = engine.connect()
    txn = conn.begin()
    try:
        inserted, updated, skipped = seed_rules(conn, force=args.force)
        print(f"\nResult: {inserted} inserted, {updated} updated, {skipped} skipped")

        if args.dry_run:
            txn.rollback()
            print("[DRY RUN] Rolled back.")
        else:
            txn.commit()
    except Exception:
        txn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
