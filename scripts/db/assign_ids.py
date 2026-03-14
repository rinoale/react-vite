#!/usr/bin/env python3
"""Assign UUIDs to new entries in source_of_truth YAML files and sort alphabetically.

For each file:
  - Entries missing an ID get a new uuid7
  - Entries are sorted alphabetically by their name/option_name field
  - File is rewritten in place

Special handling:
  - reforge.yaml: nested under weapon categories, option_id per entry, sorted within each group
  - enchant.yaml: each enchant has nested effects[], each effect also gets an ID if missing
"""
import argparse
from pathlib import Path

import yaml
from uuid_utils import uuid7


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "source_of_truth"


# ── YAML formatting ──

class LiteralStr(str):
    """Force block scalar style for multiline strings."""

def _literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|' if '\n' in data else None)

class _QuotedStr(str):
    """Marker for values that should be double-quoted."""

def _quoted_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

def _str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

def _none_representer(dumper, _data):
    return dumper.represent_scalar('tag:yaml.org,2002:null', 'null')

yaml.add_representer(str, _str_representer)
yaml.add_representer(_QuotedStr, _quoted_representer)
yaml.add_representer(type(None), _none_representer)


import re as _re
_UUID_PAT = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def _quote_values(obj):
    """Recursively wrap string values (not keys) in _QuotedStr. Leave UUIDs unquoted."""
    if isinstance(obj, dict):
        return {k: _quote_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_quote_values(v) for v in obj]
    if isinstance(obj, str):
        if _UUID_PAT.match(obj):
            return obj
        return _QuotedStr(obj)
    return obj


def _dump(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(_quote_values(data), f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=200)


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ── Flat list files (game_item, effect, echostone, murias_relic) ──

def _id_first(entry, id_field='id'):
    """Reorder dict so id_field comes first."""
    if id_field not in entry:
        return entry
    return {id_field: entry[id_field], **{k: v for k, v in entry.items() if k != id_field}}


def process_flat(path, id_field='id', sort_field='name', sort=False):
    data = _load(path) or []
    assigned = 0
    for i, entry in enumerate(data):
        if not entry.get(id_field):
            entry[id_field] = str(uuid7())
            assigned += 1
        data[i] = _id_first(entry, id_field)
    if sort:
        data.sort(key=lambda e: e.get(sort_field, ''))
    _dump(data, path)
    return len(data), assigned


# ── Reforge (nested under weapon names) ──

def process_reforge(path):
    data = _load(path) or {}
    assigned = 0
    for weapon, options in data.items():
        if not isinstance(options, list):
            continue
        for i, opt in enumerate(options):
            if not opt.get('option_id'):
                opt['option_id'] = str(uuid7())
                assigned += 1
            options[i] = {'option_name': opt.get('option_name', ''), 'option_id': opt['option_id'],
                          **{k: v for k, v in opt.items() if k not in ('option_name', 'option_id')}}
    _dump(data, path)
    total = sum(len(v) for v in data.values() if isinstance(v, list))
    return total, assigned


# ── Enchant (nested effects need IDs too) ──

def process_enchant(path):
    data = _load(path) or []
    assigned = 0
    for i, entry in enumerate(data):
        if not entry.get('id'):
            entry['id'] = str(uuid7())
            assigned += 1
        for j, eff in enumerate(entry.get('effects', [])):
            if not eff.get('id'):
                eff['id'] = str(uuid7())
                assigned += 1
            entry['effects'][j] = _id_first(eff)
        data[i] = _id_first(entry)
    _dump(data, path)
    return len(data), assigned


FILES = {
    'game_item.yaml':     {'fn': process_flat, 'kwargs': {'sort_field': 'name', 'sort': True}},
    'effect.yaml':        {'fn': process_flat, 'kwargs': {'sort_field': 'name'}},
    'echostone.yaml':     {'fn': process_flat, 'kwargs': {'sort_field': 'option_name'}},
    'murias_relic.yaml':  {'fn': process_flat, 'kwargs': {'sort_field': 'option_name'}},
    'reforge.yaml':       {'fn': process_reforge, 'kwargs': {}},
    'enchant.yaml':       {'fn': process_enchant, 'kwargs': {}},
}


def main():
    parser = argparse.ArgumentParser(description="Assign UUIDs to new source_of_truth entries and sort alphabetically.")
    parser.add_argument('files', nargs='*', help='Specific files to process (default: all)')
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    args = parser.parse_args()

    targets = args.files if args.files else list(FILES.keys())

    for filename in targets:
        if filename not in FILES:
            print(f"  ? {filename} — unknown, skipping")
            continue
        path = args.data_dir / filename
        if not path.exists():
            print(f"  ! {filename} — not found at {path}")
            continue
        spec = FILES[filename]
        total, assigned = spec['fn'](path, **spec['kwargs'])
        if assigned:
            print(f"  + {filename}: {assigned} IDs assigned, {total} entries, sorted")
        else:
            print(f"  . {filename}: {total} entries, sorted (no new IDs)")


if __name__ == '__main__':
    main()
