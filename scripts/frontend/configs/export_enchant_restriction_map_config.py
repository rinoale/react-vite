#!/usr/bin/env python3
"""Export enchant restriction map to a static JS file for frontend enchant filtering.

Reads: data/source_of_truth/enchant_restriction_map.yaml
Generates: frontend/packages/trade/public/enchant_restriction_map_config.js
"""

import json
import os
import sys

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
MAP_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'enchant_restriction_map.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'enchant_restriction_map_config.js')


def export_config():
    if not os.path.exists(MAP_PATH):
        print(f"Error: {MAP_PATH} not found")
        sys.exit(1)

    with open(MAP_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/enchant_restriction_map.yaml\n")
        f.write("window.ENCHANT_RESTRICTION_MAP = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(data)} enchant restriction mappings to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
