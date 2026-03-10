#!/usr/bin/env python3
"""Seed 100k listings with random data from existing dictionary tables.

Usage (from project root):
    python3 scripts/db/seed_listings.py [--count 100000] [--batch 5000]

Reads game_items, enchants, reforge_options, echostone_options, murias_relic_options
from the DB (already imported by import_dictionaries.py) and generates realistic
random listings with options and tags.
"""
import argparse
import random
import time

from sqlalchemy import create_engine, text


ERG_GRADES = ["S", "A", "B"]
SPECIAL_UPGRADE_TYPES = ["R", "S"]
ITEM_TYPES = ["검", "둔기", "랜스", "너클", "체인 블레이드", "스태프", "원드", "보우", "석궁", "듀얼건"]
ITEM_GRADES = ["일반", "고급", "레어", "엘리트", "크래프트"]
TAG_POOL = [
    "명품", "급처", "떨이", "협상가능", "풀개조", "풀특업",
    "풀에르그", "반피어싱", "풀피어싱", "희귀",
    "보스용", "마법사용", "근딜용", "원딜용", "힐러용",
    "초보추천", "가성비", "최상급", "올스탯", "하급",
]
TAG_POSITION_WEIGHTS = [80, 60, 30]


def _db_url_from_args(args):
    if args.database_url:
        return args.database_url
    return (
        f"postgresql+psycopg2://{args.db_user}:{args.db_password}"
        f"@{args.db_host}:{args.db_port}/{args.db_name}"
    )


def _load_lookup(conn, table, columns):
    """Load rows from a table as list of dicts."""
    cols = ", ".join(columns)
    rows = conn.execute(text(f"SELECT {cols} FROM {table}")).fetchall()
    return [dict(zip(columns, r)) for r in rows]


def _generate_listing(game_items, enchants_prefix, enchants_suffix, reforges,
                      echostones, murias_relics, user_ids):
    """Generate one random listing dict with options and tags."""
    gi = random.choice(game_items)
    prefix = random.choice(enchants_prefix) if random.random() < 0.6 else None
    suffix = random.choice(enchants_suffix) if random.random() < 0.6 else None

    # Build name: [prefix_enchant] item_name [suffix_enchant]
    parts = []
    if prefix:
        parts.append(prefix["name"])
    parts.append(gi["name"])
    if suffix:
        parts.append(suffix["name"])
    name = " ".join(parts)

    listing = {
        "user_id": random.choice(user_ids) if user_ids else None,
        "status": 1,
        "name": name,
        "price": random.choice([None, random.randint(10000, 500000000)]),
        "game_item_id": gi["id"],
        "prefix_enchant_id": prefix["id"] if prefix else None,
        "suffix_enchant_id": suffix["id"] if suffix else None,
        "item_type": random.choice(ITEM_TYPES) if random.random() < 0.5 else None,
        "item_grade": random.choice(ITEM_GRADES) if random.random() < 0.3 else None,
        "erg_grade": random.choice(ERG_GRADES) if random.random() < 0.4 else None,
        "erg_level": random.randint(1, 50) if random.random() < 0.4 else None,
        "special_upgrade_type": random.choice(SPECIAL_UPGRADE_TYPES) if random.random() < 0.3 else None,
        "special_upgrade_level": random.randint(1, 7) if random.random() < 0.3 else None,
        "damage": random.randint(50, 500) if random.random() < 0.5 else None,
        "magic_damage": random.randint(50, 400) if random.random() < 0.3 else None,
        "balance": random.randint(30, 80) if random.random() < 0.5 else None,
        "defense": random.randint(1, 30) if random.random() < 0.3 else None,
        "protection": random.randint(1, 20) if random.random() < 0.3 else None,
        "durability": random.randint(5, 20) if random.random() < 0.4 else None,
        "piercing_level": random.randint(1, 5) if random.random() < 0.2 else None,
    }

    options = []
    # Reforge options (1-3)
    if reforges and random.random() < 0.7:
        for rf in random.sample(reforges, min(random.randint(1, 3), len(reforges))):
            max_lv = random.choice([10, 15, 20])
            options.append({
                "option_type": "reforge_options",
                "option_id": rf["id"],
                "option_name": rf["option_name"],
                "rolled_value": random.randint(1, max_lv + 5),
                "max_level": max_lv,
            })

    # Echostone options (0-2)
    if echostones and random.random() < 0.4:
        for es in random.sample(echostones, min(random.randint(1, 2), len(echostones))):
            max_lv = es["max_level"] or 10
            options.append({
                "option_type": "echostone_options",
                "option_id": es["id"],
                "option_name": es["option_name"],
                "rolled_value": random.randint(es.get("min_level", 1), max_lv),
                "max_level": max_lv,
            })

    # Murias relic options (0-2)
    if murias_relics and random.random() < 0.3:
        for mr in random.sample(murias_relics, min(random.randint(1, 2), len(murias_relics))):
            max_lv = mr["max_level"] or 10
            options.append({
                "option_type": "murias_relic_options",
                "option_id": mr["id"],
                "option_name": mr["option_name"],
                "rolled_value": random.randint(mr.get("min_level", 1), max_lv),
                "max_level": max_lv,
            })

    # Tags (1-3)
    tag_names = random.sample(TAG_POOL, random.randint(1, 3))
    # Sometimes add enchant name as tag
    if prefix and random.random() < 0.5:
        tag_names.append(prefix["name"])
    if suffix and random.random() < 0.5:
        tag_names.append(suffix["name"])

    return listing, options, tag_names


def main():
    parser = argparse.ArgumentParser(description="Seed random listings for load testing.")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name", default="mabinogi")
    parser.add_argument("--db-user", default="mabinogi")
    parser.add_argument("--db-password", default="mabinogi")
    parser.add_argument("--count", type=int, default=100_000, help="Number of listings to create")
    parser.add_argument("--batch", type=int, default=5000, help="Batch size for commits")
    args = parser.parse_args()

    db_url = _db_url_from_args(args)
    engine = create_engine(db_url, pool_pre_ping=True)

    # Load lookup data
    with engine.connect() as conn:
        game_items = _load_lookup(conn, "game_items", ["id", "name"])
        enchants_all = _load_lookup(conn, "enchants", ["id", "name", "slot"])
        reforges = _load_lookup(conn, "reforge_options", ["id", "option_name"])
        echostones = _load_lookup(conn, "echostone_options", ["id", "option_name", "max_level", "min_level"])
        murias_relics = _load_lookup(conn, "murias_relic_options", ["id", "option_name", "max_level", "min_level"])
        user_rows = conn.execute(text("SELECT id FROM users")).fetchall()
        user_ids = [r[0] for r in user_rows] or [None]

    enchants_prefix = [e for e in enchants_all if e["slot"] == 0]
    enchants_suffix = [e for e in enchants_all if e["slot"] == 1]

    if not game_items:
        print("ERROR: No game_items found. Run import_dictionaries.py first.")
        return
    if not enchants_all:
        print("ERROR: No enchants found. Run import_dictionaries.py first.")
        return

    print(f"Loaded: {len(game_items)} game_items, {len(enchants_prefix)} prefix / {len(enchants_suffix)} suffix enchants, "
          f"{len(reforges)} reforges, {len(echostones)} echostones, {len(murias_relics)} murias_relics, {len(user_ids)} users")
    print(f"Generating {args.count:,} listings in batches of {args.batch:,}...")

    # Pre-create tags
    tag_name_to_id = {}
    with engine.begin() as conn:
        for name in TAG_POOL:
            row = conn.execute(
                text("INSERT INTO tags (name, weight) VALUES (:n, :w) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id"),
                {"n": name, "w": random.randint(0, 170)},
            ).fetchone()
            tag_name_to_id[name] = row[0]
        # Also pre-create enchant name tags
        for e in enchants_all:
            if e["name"] not in tag_name_to_id:
                row = conn.execute(
                    text("INSERT INTO tags (name, weight) VALUES (:n, 0) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id"),
                    {"n": e["name"]},
                ).fetchone()
                tag_name_to_id[e["name"]] = row[0]

    print(f"Pre-created {len(tag_name_to_id)} tags")

    t0 = time.time()
    total = 0

    for batch_start in range(0, args.count, args.batch):
        batch_end = min(batch_start + args.batch, args.count)
        batch_size = batch_end - batch_start

        with engine.begin() as conn:
            for _ in range(batch_size):
                listing, options, tag_names = _generate_listing(
                    game_items, enchants_prefix, enchants_suffix,
                    reforges, echostones, murias_relics, user_ids,
                )

                # Insert listing
                cols = [k for k, v in listing.items() if v is not None]
                placeholders = ", ".join(f":{c}" for c in cols)
                col_names = ", ".join(cols)
                row = conn.execute(
                    text(f"INSERT INTO listings ({col_names}) VALUES ({placeholders}) RETURNING id"),
                    {c: listing[c] for c in cols},
                ).fetchone()
                listing_id = row[0]

                # Insert options
                for opt in options:
                    conn.execute(
                        text(
                            "INSERT INTO listing_options (listing_id, option_type, option_id, option_name, rolled_value, max_level) "
                            "VALUES (:lid, :otype, :oid, :oname, :rv, :ml)"
                        ),
                        {"lid": listing_id, "otype": opt["option_type"], "oid": opt["option_id"],
                         "oname": opt["option_name"], "rv": opt["rolled_value"], "ml": opt["max_level"]},
                    )

                # Insert tag targets
                for i, tname in enumerate(tag_names[:5]):
                    tag_id = tag_name_to_id.get(tname)
                    if not tag_id:
                        continue
                    w = TAG_POSITION_WEIGHTS[i] if i < len(TAG_POSITION_WEIGHTS) else 0
                    conn.execute(
                        text(
                            "INSERT INTO tag_targets (tag_id, target_type, target_id, weight) "
                            "VALUES (:tid, 'listing', :lid, :w) "
                            "ON CONFLICT (tag_id, target_type, target_id) DO NOTHING"
                        ),
                        {"tid": tag_id, "lid": listing_id, "w": w},
                    )

        total += batch_size
        elapsed = time.time() - t0
        rate = total / elapsed if elapsed > 0 else 0
        print(f"  {total:>7,} / {args.count:,}  ({rate:.0f} listings/s)")

    elapsed = time.time() - t0
    print(f"\nDone: {total:,} listings in {elapsed:.1f}s ({total / elapsed:.0f}/s)")


if __name__ == "__main__":
    main()
