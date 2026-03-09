#!/usr/bin/env python3
"""Export echostone options to a static JS file for frontend client-side searching.

Run from project root:
    python3 scripts/frontend/configs/export_echostone_config.py
"""

import json
import os
import sys
from sqlalchemy import text

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.append(os.path.join(PROJECT_ROOT, 'backend'))
from db.connector import SessionLocal

_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'echostone_config.js')


def export_config():
    db = SessionLocal()
    try:
        print("Fetching echostone options from database...")
        rows = db.execute(
            text("SELECT id, option_name, type, max_level, min_level FROM echostone_options ORDER BY option_name")
        ).mappings()

        options = [
            {
                "id": r["id"],
                "option_name": r["option_name"],
                "type": r["type"],
                "max_level": r["max_level"],
                "min_level": r["min_level"],
            }
            for r in rows
        ]

        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("// Generated static config for client-side echostone searching\n")
            f.write("window.ECHOSTONE_CONFIG = ")
            json.dump(options, f, ensure_ascii=False, indent=2)
            f.write(";\n")

        print(f"Successfully exported {len(options)} echostone options to {OUTPUT_PATH}")

    except Exception as e:
        print(f"Error exporting config: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    export_config()
