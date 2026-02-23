#!/usr/bin/env python3
"""Remove stale OCR crop directories.

Deletes tmp/ocr_crops/{session_id}/ dirs older than --max-age hours
that have no associated corrections in the database.

Usage:
    python3 scripts/ocr/cleanup_crops.py                # default: 24h
    python3 scripts/ocr/cleanup_crops.py --max-age 48   # 48h
    python3 scripts/ocr/cleanup_crops.py --dry-run       # show what would be deleted
"""

import argparse
import os
import shutil
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CROPS_DIR = os.path.join(PROJECT_ROOT, 'tmp', 'ocr_crops')

sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))


def main():
    parser = argparse.ArgumentParser(description='Clean up stale OCR crop directories')
    parser.add_argument('--max-age', type=float, default=24,
                        help='Max age in hours before deletion (default: 24)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without deleting')
    args = parser.parse_args()

    if not os.path.isdir(CROPS_DIR):
        print(f"Crops dir does not exist: {CROPS_DIR}")
        return

    # Try connecting to DB to check for associated corrections
    db = None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from db.connector import _build_database_url
        from db.models import OcrCorrection

        engine = create_engine(_build_database_url())
        Session = sessionmaker(bind=engine)
        db = Session()
    except Exception as e:
        print(f"WARNING: Cannot connect to DB ({e}), will skip correction check")

    cutoff = time.time() - args.max_age * 3600
    removed = 0
    kept = 0

    for session_id in sorted(os.listdir(CROPS_DIR)):
        session_dir = os.path.join(CROPS_DIR, session_id)
        if not os.path.isdir(session_dir):
            continue

        mtime = os.path.getmtime(session_dir)
        if mtime >= cutoff:
            kept += 1
            continue

        # Check if any corrections reference this session
        if db is not None:
            count = db.query(OcrCorrection).filter(
                OcrCorrection.session_id == session_id
            ).count()
            if count > 0:
                kept += 1
                continue

        age_h = (time.time() - mtime) / 3600
        if args.dry_run:
            print(f"  Would delete: {session_id} (age: {age_h:.1f}h)")
        else:
            shutil.rmtree(session_dir)
            print(f"  Deleted: {session_id} (age: {age_h:.1f}h)")
        removed += 1

    if db is not None:
        db.close()

    action = "Would delete" if args.dry_run else "Deleted"
    print(f"\n{action}: {removed}, Kept: {kept}")


if __name__ == '__main__':
    main()
