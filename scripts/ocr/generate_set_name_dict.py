#!/usr/bin/env python3
"""Generate set_name.txt from game_item.yaml (source of truth).

Extracts set names from items matching '세트 효과 {name} (강화|증가) +N 주문서'
and outputs '{name} (강화|증가)' per line.

Outputs:
  data/dictionary/set_name.txt — FM dictionary (with 강화/증가 suffix)

Run from project root:
    python3 scripts/ocr/generate_set_name_dict.py
"""

import os
import re

import yaml

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
GAME_ITEM_YAML = os.path.join(_PROJECT_ROOT, 'data', 'source_of_truth', 'game_item.yaml')
SET_NAME_TXT = os.path.join(_PROJECT_ROOT, 'data', 'dictionary', 'set_name.txt')

_SET_EFFECT_RE = re.compile(r'^세트 효과\s+(.+(?:강화|증가))\s+\+\d+\s+주문서$')


def main():
    with open(GAME_ITEM_YAML, 'r', encoding='utf-8') as f:
        items = yaml.safe_load(f) or []

    seen = set()
    names = []
    for item in items:
        m = _SET_EFFECT_RE.match(item['name'].strip())
        if m:
            name = m.group(1).strip()
            if name not in seen:
                seen.add(name)
                names.append(name)

    names.sort()

    with open(SET_NAME_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(names) + '\n')
    print(f"Wrote {len(names)} set names → {os.path.basename(SET_NAME_TXT)}")

    # Print trimmed names for frontend constant
    trimmed = sorted(set(re.sub(r'\s*(강화|증가)$', '', n) for n in names))
    print(f"\nFrontend SET_NAMES constant ({len(trimmed)} entries):")
    for t in trimmed:
        print(f"  '{t}',")


if __name__ == '__main__':
    main()
