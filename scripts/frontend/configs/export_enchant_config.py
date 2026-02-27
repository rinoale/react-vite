#!/usr/bin/env python3
"""Export enchant metadata to a static JS file for frontend client-side searching.

Combines YAML metadata with Database IDs.
Generates: frontend/public/enchants_config.js
"""

import json
import os
import re
import sys
import yaml
from sqlalchemy import text

# Matches first number or range pattern: "16", "0.3", "8 ~ 9", "50 ~ 65"
_NUM_RE = re.compile(r'\d+(?:\.\d+)?(?:\s*~\s*\d+(?:\.\d+)?)?')

# Add backend to path to import connector
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.append(os.path.join(PROJECT_ROOT, 'backend'))
from db.connector import SessionLocal

SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'enchant.yaml')
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'packages', 'trade', 'public', 'enchants_config.js')

RANK_MAP = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15
}

def get_rank_int(rank_str):
    rank_str = str(rank_str).upper()
    try:
        if rank_str in RANK_MAP:
            return RANK_MAP[rank_str]
        return int(rank_str)
    except ValueError:
        return rank_str

def export_config():
    if not os.path.exists(SOURCE_PATH):
        print(f"Error: Source file not found at {SOURCE_PATH}")
        return

    db = SessionLocal()
    try:
        print(f"Reading enchants from {SOURCE_PATH}...")
        with open(SOURCE_PATH, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)

        print("Fetching IDs from database...")
        # Get all enchants from DB once to avoid 1100+ individual queries
        # (name, rank, slot) -> id
        db_rows = db.execute(
            text("SELECT id, name, rank, slot FROM enchants")
        ).mappings()

        # Build a lookup map: (name, rank_int, slot_int) -> id
        # slot: '접두' -> 0, '접미' -> 1
        id_map = {}
        for r in db_rows:
            key = (r['name'], r['rank'], r['slot'])
            id_map[key] = r['id']

        # Fetch all enchant_effects in one query, keyed by enchant_id
        # Each effect's enchant_effect_id allows direct FK matching at registration
        ee_rows = db.execute(
            text("SELECT id, enchant_id, effect_order FROM enchant_effects ORDER BY enchant_id, effect_order")
        ).mappings()
        ee_map = {}  # enchant_id -> [enchant_effect_id ordered by effect_order]
        for r in ee_rows:
            ee_map.setdefault(r['enchant_id'], []).append(r['id'])

        exported_data = []
        for item in yaml_data:
            name = item.get('name')
            rank_str = item.get('rank')
            slot_str = item.get('slot') # '접두' or '접미'
            
            rank_int = get_rank_int(rank_str)
            slot_int = 0 if slot_str == '접두' else 1
            
            key = (name, rank_int, slot_int)
            db_id = id_map.get(key)
            
            if db_id is None:
                print(f"Warning: No DB ID found for {slot_str} {name} (Rank {rank_str})")
                continue
                
            # Build structured effects: each is {enchant_effect_id, text, option_name, suffix, ranged}
            # so the frontend can reconstruct corrected text without regex
            # and send enchant_effect_id for direct FK matching at registration.
            ee_ids = ee_map.get(db_id, [])
            effects_list = []
            for eff_idx, eff in enumerate(item.get('effects', [])):
                if isinstance(eff, str):
                    eff_text = eff
                    parse_text = eff
                elif isinstance(eff, dict):
                    cond = eff.get('condition', '')
                    effect = eff.get('effect', '')
                    eff_text = f"{cond} {effect}".strip() if cond and effect \
                        else (effect or cond)
                    # Parse option_name from effect part only (not merged text)
                    # so it matches OCR-detected option_name which sees no condition
                    parse_text = effect if effect else eff_text
                else:
                    continue

                # YAML effects and DB enchant_effects share the same ordering
                ee_id = ee_ids[eff_idx] if eff_idx < len(ee_ids) else None

                m = _NUM_RE.search(parse_text)
                if m:
                    oname = parse_text[:m.start()].rstrip()
                    is_ranged = '~' in m.group()
                    eff_entry = {
                        'enchant_effect_id': ee_id,
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
                        'enchant_effect_id': ee_id,
                        'text': eff_text,
                        'option_name': None,
                        'suffix': None,
                        'ranged': False,
                    })

            entry = {
                'id': db_id,
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
            # Optional: add synonym for searchability if present
            if 'synonym' in item:
                entry['synonym'] = item['synonym']
                
            exported_data.append(entry)

        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("// Generated static config for client-side searching\n")
            f.write("window.ENCHANTS_CONFIG = ")
            json.dump(exported_data, f, ensure_ascii=False, indent=2)
            f.write(";\n")
            
        print(f"Successfully exported {len(exported_data)} enchants to {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"Error exporting config: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    export_config()
