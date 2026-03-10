#!/usr/bin/env python3
"""Run all frontend config export scripts.

Generates static JS config files that the frontend reads at runtime.
Requires a running PostgreSQL database with imported dictionaries.

Run from project root:
    python3 scripts/frontend/configs/export_all.py
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..', '..')

SCRIPTS = [
    os.path.join(SCRIPT_DIR, 'export_enchant_config.py'),
    os.path.join(SCRIPT_DIR, 'export_reforge_config.py'),
    os.path.join(SCRIPT_DIR, 'export_game_items_config.py'),
    os.path.join(SCRIPT_DIR, 'export_echostone_config.py'),
    os.path.join(SCRIPT_DIR, 'export_murias_relic_config.py'),
]


def main():
    failed = []
    for script in SCRIPTS:
        name = os.path.basename(script)
        print(f"\n{'='*60}")
        print(f"Running {name}...")
        print('='*60)
        result = subprocess.run(
            [sys.executable, script],
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            failed.append(name)

    print(f"\n{'='*60}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All configs exported successfully.")


if __name__ == '__main__':
    main()
