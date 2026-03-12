#!/usr/bin/env python3
"""Export game items to a static JS file for frontend client-side searching.

Reads: data/source_of_truth/game_item.yaml
Generates: frontend/packages/trade/public/game_items_config.js
"""

import json
import os
import sys

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'game_item.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'game_items_config.js')


def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: {SOURCE_PATH} not found")
        sys.exit(1)

    print(f"Reading game items from {SOURCE_PATH}...")
    with open(SOURCE_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or []

    items = [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item.get("type"),
            "searchable": item.get("searchable", False),
            "tradable": item.get("tradable", True),
        }
        for item in data
    ]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/game_item.yaml\n")
        f.write("window.GAME_ITEMS_CONFIG = ")
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(items)} game items to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
