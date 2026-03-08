#!/usr/bin/env python3
"""Export game items to a static JS file for frontend client-side searching.

Generates: frontend/packages/trade/public/game_items_config.js
"""

import json
import os
import sys
from sqlalchemy import text

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.append(os.path.join(PROJECT_ROOT, 'backend'))
from db.connector import SessionLocal

_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'game_items_config.js')


def export_config():
    db = SessionLocal()
    try:
        print("Fetching game items from database...")
        rows = db.execute(
            text("SELECT id, name FROM game_items ORDER BY name")
        ).mappings()

        items = [{"id": r["id"], "name": r["name"]} for r in rows]

        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("// Generated static config for client-side game item lookup\n")
            f.write("window.GAME_ITEMS_CONFIG = ")
            json.dump(items, f, ensure_ascii=False, indent=2)
            f.write(";\n")

        print(f"Successfully exported {len(items)} game items to {OUTPUT_PATH}")

    except Exception as e:
        print(f"Error exporting config: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    export_config()
