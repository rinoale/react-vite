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
        "name": "enchant_names",
        "description": "Create tag for each enchant name",
        "rule_type": "iterate_list",
        "priority": 10,
        "config": {"source": "enchants", "field": "name", "tag_template": "{value}"},
    },
    {
        "name": "erg_max",
        "description": "Tag when erg level reaches max (50)",
        "rule_type": "field_compare",
        "priority": 20,
        "config": {
            "conditions": [
                {"field": "erg_grade", "op": "!=", "value": None},
                {"field": "erg_level", "op": "==", "value": 50},
            ],
            "tag_template": "{erg_grade}르그{erg_level}",
        },
    },
    {
        "name": "special_upgrade_name",
        "description": "Map special upgrade type to nickname (R=붉개, S=푸개)",
        "rule_type": "value_map",
        "priority": 30,
        "config": {"field": "special_upgrade_type", "mapping": {"R": "붉개", "S": "푸개"}},
    },
    {
        "name": "special_upgrade_level",
        "description": "Tag high special upgrade level (7+)",
        "rule_type": "field_compare",
        "priority": 40,
        "config": {
            "conditions": [{"field": "special_upgrade_level", "op": ">=", "value": 7}],
            "tag_template": "{special_upgrade_level}강",
        },
    },
    {
        "name": "full_piercing",
        "description": "Tag when piercing level equals max roll",
        "rule_type": "cross_table",
        "priority": 50,
        "config": {
            "source": "listing_options",
            "filter": {"option_type": "enchant_effects", "option_name": "피어싱 레벨"},
            "lookup_table": "enchant_effects",
            "lookup_key": "option_id",
            "lookup_field": "max_value",
            "compare_field": "rolled_value",
            "op": ">=",
            "tag_template": "풀피어싱",
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
