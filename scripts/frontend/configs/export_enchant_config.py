#!/usr/bin/env python3
"""Export enchant metadata to a static JS file for frontend client-side searching.

Combines YAML metadata with Database IDs.
Generates: frontend/public/enchants_config.js
"""

import json
import os
import sys
import yaml
from sqlalchemy import text

# Add backend to path to import connector
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.append(os.path.join(PROJECT_ROOT, 'backend'))
from db.connector import SessionLocal

SOURCE_PATH = os.path.join(PROJECT_ROOT, 'data', 'source_of_truth', 'enchant.yaml')
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'public', 'enchants_config.js')

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
                
            entry = {
                'id': db_id,
                'name': name,
                'slot': slot_int,
                'rank': rank_int,
                'rank_label': str(rank_str).upper()
            }
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
