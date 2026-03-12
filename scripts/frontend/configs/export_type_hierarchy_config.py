#!/usr/bin/env python3
"""Export type hierarchy to a static JS file for frontend ancestor chain lookups.

Reads: data/source_of_truth/type_hierarchy.yaml
Generates: frontend/packages/trade/public/type_hierarchy_config.js
"""

import json
import os
import sys

import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
HIERARCHY_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'type_hierarchy.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'type_hierarchy_config.js')


def export_config():
    if not os.path.exists(HIERARCHY_PATH):
        print(f"Error: {HIERARCHY_PATH} not found")
        sys.exit(1)

    with open(HIERARCHY_PATH, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    # Count nodes
    def count_nodes(d):
        if d is None:
            return 1, 0  # leaf, not mid
        if not isinstance(d, dict):
            return 0, 0
        leaves = 0
        mids = 0
        for v in d.values():
            if v is None:
                leaves += 1
            else:
                mids += 1
                l, m = count_nodes(v)
                leaves += l
                mids += m
        return leaves, mids

    leaf_count, mid_count = count_nodes(data)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/type_hierarchy.yaml\n")
        f.write("window.TYPE_HIERARCHY = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported type hierarchy ({leaf_count} leaves, {mid_count} mid-level nodes) to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
