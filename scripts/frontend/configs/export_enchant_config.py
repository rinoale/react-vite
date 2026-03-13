#!/usr/bin/env python3
"""Export enchant metadata to a static JS file for frontend client-side searching.

Reads: data/source_of_truth/enchant.yaml (IDs included in YAML)
Generates: frontend/packages/trade/public/enchants_config.js

No DB needed -- all IDs (enchant, effect) come from YAML.
"""

import json
import os
import re
import sys

import yaml

# Matches first number or range pattern: "16", "0.3", "8 ~ 9", "50 ~ 65"
_NUM_RE = re.compile(r'\d+(?:\.\d+)?(?:\s*~\s*\d+(?:\.\d+)?)?')

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'enchant.yaml')
_FRONTEND_DIR = os.environ.get('FRONTEND_DIST_DIR', os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public'))
OUTPUT_PATH = os.path.join(_FRONTEND_DIR, 'enchants_config.js')

RANK_MAP = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15
}


def get_rank_int(rank_str):
    rank_str = str(rank_str).upper()
    if rank_str in RANK_MAP:
        return RANK_MAP[rank_str]
    try:
        return int(rank_str)
    except ValueError:
        return rank_str


def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: Source file not found at {SOURCE_PATH}")
        sys.exit(1)

    print(f"Reading enchants from {SOURCE_PATH}...")
    with open(SOURCE_PATH, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f)

    exported_data = []
    for item in yaml_data:
        name = item.get('name')
        rank_str = item.get('rank')
        slot_str = item.get('slot')  # '접두' or '접미'
        enchant_id = item.get('id')

        rank_int = get_rank_int(rank_str)
        slot_int = 0 if slot_str == '접두' else 1

        # Build structured effects: each is {effect_id, text, option_name, suffix, ranged}
        # so the frontend can reconstruct corrected text without regex.
        effects_list = []
        for eff in item.get('effects', []):
            if isinstance(eff, dict):
                cond = eff.get('condition', '')
                effect = eff.get('effect', '')
                eff_text = f"{cond} {effect}".strip() if cond and effect \
                    else (effect or cond)
                # Parse option_name from effect part only (not merged text)
                # so it matches OCR-detected option_name which sees no condition
                parse_text = effect if effect else eff_text
                ee_id = eff.get('id')
            else:
                continue

            m = _NUM_RE.search(parse_text)
            if m:
                oname = parse_text[:m.start()].rstrip()
                is_ranged = '~' in m.group()
                eff_entry = {
                    'id': ee_id,
                    'text': eff_text,
                    'option_name': oname if oname else None,
                    'suffix': parse_text[m.end():],
                    'ranged': is_ranged,
                }
                if is_ranged:
                    parts = m.group().split('~')
                    lo = parts[0].strip()
                    hi = parts[1].strip()
                    eff_entry['min'] = float(lo) if '.' in lo else int(lo)
                    eff_entry['max'] = float(hi) if '.' in hi else int(hi)
                effects_list.append(eff_entry)
            else:
                effects_list.append({
                    'id': ee_id,
                    'text': eff_text,
                    'option_name': None,
                    'suffix': None,
                    'ranged': False,
                })

        entry = {
            'id': enchant_id,
            'name': name,
            'slot': slot_int,
            'rank': rank_int,
            'rank_label': str(rank_str).upper(),
            'effects': effects_list,
        }
        # Pass through metadata fields
        if 'restriction' in item:
            entry['restriction'] = item['restriction']
        if item.get('binding'):
            entry['binding'] = True
        if item.get('guaranteed_success'):
            entry['guaranteed_success'] = True
        if 'activation' in item:
            entry['activation'] = item['activation']
        if 'credit' in item:
            entry['credit'] = item['credit']
        if 'synonym' in item:
            entry['synonym'] = item['synonym']

        exported_data.append(entry)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write("// Generated from data/source_of_truth/enchant.yaml\n")
        f.write("window.ENCHANTS_CONFIG = ")
        json.dump(exported_data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully exported {len(exported_data)} enchants to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_config()
