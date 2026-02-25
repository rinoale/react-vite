#!/usr/bin/env python3
"""Export reforge options to a static JS file for frontend client-side searching.

Reads data/dictionary/reforge.txt and generates frontend/public/reforges_config.js.

Run from project root:
    python3 scripts/frontend/configs/export_reforge_config.py
"""

import json
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'dictionary', 'reforge.txt')
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'public', 'reforges_config.js')


def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: Source file not found at {SOURCE_PATH}")
        return

    print(f"Reading reforge options from {SOURCE_PATH}...")
    seen = set()
    options = []
    with open(SOURCE_PATH, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            options.append(line)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated static config for client-side reforge searching\n")
        f.write("window.REFORGES_CONFIG = ")
        json.dump(options, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(options)} reforge options to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
