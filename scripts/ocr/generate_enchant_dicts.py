#!/usr/bin/env python3
"""Generate enchant dictionary text files from enchant.yaml (source of truth).

Outputs:
  enchant_slot_header.txt — one OCR-visible header line per enchant
  enchant_effect.txt      — deduplicated, sorted effect lines

Rank visibility rule for slot headers:
  Rank A-F: white text in-game → visible in white-mask crop → include rank
  Rank 1-9: pink text in-game → invisible in white-mask crop → omit rank

Run from project root:
    python3 scripts/ocr/generate_enchant_dicts.py
"""

import os

import yaml

DICT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'dictionary')
ENCHANT_YAML = os.path.join(os.path.dirname(__file__), '..', 'data', 'source_of_truth', 'enchant.yaml')
SLOT_HEADER_TXT = os.path.join(DICT_DIR, 'enchant_slot_header.txt')
EFFECT_TXT = os.path.join(DICT_DIR, 'enchant_effect.txt')


def main():
    with open(ENCHANT_YAML, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Slot headers (deduplicated — rank-1-9 entries with same name+slot collapse)
    seen_headers = set()
    headers = []
    for e in data:
        rank = str(e['rank'])
        if rank.isalpha():  # A-F: rank visible in crop
            line = f"[{e['slot']}] {e['name']} (랭크 {rank})"
        else:  # 1-9: rank not visible in crop
            line = f"[{e['slot']}] {e['name']}"
        if line not in seen_headers:
            seen_headers.add(line)
            headers.append(line)

    with open(SLOT_HEADER_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(headers) + '\n')
    print(f"Wrote {len(headers)} unique lines → {os.path.basename(SLOT_HEADER_TXT)}")

    # Effects (deduplicated, sorted)
    effects = set()
    for e in data:
        for eff in e.get('effects', []):
            effects.add(eff)
    sorted_effects = sorted(effects)

    with open(EFFECT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted_effects) + '\n')
    print(f"Wrote {len(sorted_effects)} unique effects → {os.path.basename(EFFECT_TXT)}")


if __name__ == '__main__':
    main()
