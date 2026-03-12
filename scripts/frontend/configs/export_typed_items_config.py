#!/usr/bin/env python3
"""Export typed items to a static JS file for frontend search bar.

Reads: data/source_of_truth/typed_item.yaml + game_items DB table (for IDs)
Generates: frontend/packages/trade/public/typed_items_config.js
"""

import json
import os
import sys

import yaml
from sqlalchemy import text

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.append(os.path.join(PROJECT_ROOT, 'backend'))
from db.connector import SessionLocal

TYPED_ITEM_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'typed_item.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'typed_items_config.js')


def export_config():
    if not os.path.exists(TYPED_ITEM_PATH):
        print(f"Error: {TYPED_ITEM_PATH} not found")
        return

    with open(TYPED_ITEM_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or []

    # Look up IDs from game_items table
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, name FROM game_items")).mappings()
        name_to_id = {r["name"]: r["id"] for r in rows}
    finally:
        db.close()

    items = []
    missing = []
    for item in data:
        name = item["name"]
        gid = name_to_id.get(name)
        if gid is None:
            missing.append(name)
        items.append({"id": gid, "name": name, "type": item.get("type", "")})

    if missing:
        print(f"Warning: {len(missing)} items not found in game_items DB: {missing[:5]}...")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/typed_item.yaml + game_items DB\n")
        f.write("window.TYPED_ITEMS_CONFIG = ")
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(items)} typed items ({len(items) - len(missing)} with IDs) to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
