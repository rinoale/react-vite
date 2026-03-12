#!/usr/bin/env python3
"""Export reforge data to static JS files for frontend.

Reads: data/source_of_truth/reforge.yaml
Generates: frontend/packages/trade/public/reforges_config.js

Exports two globals:
- REFORGES_CONFIG: nested [{name, options: [{option_id, option_name, min_level, max_level, ...}]}]
- REFORGE_OPTIONS_CONFIG: flat deduplicated [{option_id, option_name}] (for search dropdowns)
"""

import json
import os
import sys

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'reforge.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'reforges_config.js')


def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: {SOURCE_PATH} not found")
        sys.exit(1)

    print(f"Reading reforge data from {SOURCE_PATH}...")
    with open(SOURCE_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    reforges = []
    seen = set()
    flat_options = []

    for reforge_name, entries in data.items():
        options = []
        for entry in entries:
            options.append({
                "option_id": entry["option_id"],
                "option_name": entry["option_name"],
                "min_level": entry["min_level"],
                "max_level": entry["max_level"],
                "transcend_max_level": entry.get("transcend_max_level"),
            })
            if entry["option_id"] not in seen:
                seen.add(entry["option_id"])
                flat_options.append({
                    "option_id": entry["option_id"],
                    "option_name": entry["option_name"],
                })
        reforges.append({
            "name": reforge_name,
            "options": options,
        })

    reforges.sort(key=lambda x: x["name"])
    flat_options.sort(key=lambda x: x["option_name"])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/reforge.yaml\n")
        f.write("window.REFORGES_CONFIG = ")
        json.dump(reforges, f, ensure_ascii=False, indent=2)
        f.write(";\nwindow.REFORGE_OPTIONS_CONFIG = ")
        json.dump(flat_options, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    option_count = sum(len(r["options"]) for r in reforges)
    print(f"Successfully exported {len(reforges)} reforges ({option_count} options, {len(flat_options)} unique) to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
