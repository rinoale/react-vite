#!/usr/bin/env python3
"""Export echostone options to a static JS file for frontend client-side searching.

Reads: data/source_of_truth/echostone.yaml
Generates: frontend/packages/trade/public/echostone_config.js
"""

import json
import os
import sys

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'echostone.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'echostone_config.js')


def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: {SOURCE_PATH} not found")
        sys.exit(1)

    print(f"Reading echostone options from {SOURCE_PATH}...")
    with open(SOURCE_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or []

    options = [
        {
            "id": item["id"],
            "option_name": item["option_name"],
            "type": item["type"],
            "max_level": item["max_level"],
            "min_level": item["min_level"],
        }
        for item in data
    ]

    options.sort(key=lambda x: x["option_name"])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/echostone.yaml\n")
        f.write("window.ECHOSTONE_CONFIG = ")
        json.dump(options, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(options)} echostone options to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
