#!/usr/bin/env python3
"""Merge approved user corrections into a new training version.

Usage:
    python3 scripts/ocr/merge_corrections.py \
        --model general_mabinogi_classic \
        --base-version a19 --new-version a19.1 \
        --duplication 3

Steps:
  1. Query DB for corrections with status='approved'
  2. Charset-validate against base version's unique_chars.txt
  3. Create new version dir with training data from base + corrections
  4. Update DB rows: status='trained', trained_version=new_version
"""

import argparse
import os
import shutil
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.connector import _build_database_url
from db.models import OcrCorrection


def load_charset(version_dir):
    path = os.path.join(version_dir, 'unique_chars.txt')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return set(f.read().strip())


def main():
    parser = argparse.ArgumentParser(description='Merge corrections into training data')
    parser.add_argument('--model', required=True,
                        choices=['general_mabinogi_classic', 'general_nanum_gothic_bold', 'general'],
                        help='Model type')
    parser.add_argument('--base-version', required=True, help='Base version to copy from (e.g. a19)')
    parser.add_argument('--new-version', required=True, help='New version to create (e.g. a19.1)')
    parser.add_argument('--duplication', type=int, default=3,
                        help='How many times to duplicate correction images (default: 3)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing')
    args = parser.parse_args()

    # Import model version utilities
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts', 'ocr', 'lib'))
    from model_version import _MODEL_TYPES, version_dir

    model_type = args.model
    prefix, _ = _MODEL_TYPES[model_type]

    base_dir = version_dir(model_type, args.base_version)
    new_dir = version_dir(model_type, args.new_version)

    if not os.path.isdir(base_dir):
        print(f"ERROR: Base version dir not found: {base_dir}")
        sys.exit(1)

    if os.path.exists(new_dir):
        print(f"ERROR: New version dir already exists: {new_dir}")
        sys.exit(1)

    charset = load_charset(base_dir)
    if charset is None:
        print(f"WARNING: No unique_chars.txt in {base_dir}, skipping charset validation")

    # Connect to DB
    engine = create_engine(_build_database_url())
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        rows = db.query(OcrCorrection).filter(OcrCorrection.status == 'approved').all()
        if not rows:
            print("No approved corrections found.")
            return

        # Charset-validate
        valid_rows = []
        corrections_dir = os.path.join(PROJECT_ROOT, 'data', 'corrections')
        for row in rows:
            if charset:
                bad = set(row.corrected_text) - charset - {' '}
                if bad:
                    print(f"  SKIP correction #{row.id}: chars {bad} not in charset")
                    continue
            # Check image exists
            img_path = os.path.join(corrections_dir, row.session_id, row.image_filename)
            if not os.path.isfile(img_path):
                print(f"  SKIP correction #{row.id}: image not found: {img_path}")
                continue
            valid_rows.append((row, img_path))

        print(f"Approved: {len(rows)}, Valid: {len(valid_rows)}, Duplication: {args.duplication}")

        if not valid_rows:
            print("No valid corrections to merge.")
            return

        if args.dry_run:
            print("\n[DRY RUN] Would create:")
            print(f"  {new_dir}/")
            print(f"  Copy base training data from {base_dir}/train_data/")
            print(f"  Add {len(valid_rows) * args.duplication} correction images")
            return

        # Create new version dir structure
        os.makedirs(new_dir, exist_ok=True)

        # Copy base configs
        for fname in ('training_config.yaml', 'unique_chars.txt'):
            src = os.path.join(base_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(new_dir, fname))

        # Copy base training data
        base_train = os.path.join(base_dir, 'train_data')
        new_train = os.path.join(new_dir, 'train_data')
        new_images = os.path.join(new_train, 'images')
        new_labels = os.path.join(new_train, 'labels')

        if os.path.isdir(base_train):
            shutil.copytree(base_train, new_train)
        else:
            os.makedirs(new_images, exist_ok=True)
            os.makedirs(new_labels, exist_ok=True)

        os.makedirs(new_images, exist_ok=True)
        os.makedirs(new_labels, exist_ok=True)

        # Find next index in images dir
        existing = [f for f in os.listdir(new_images) if f.endswith('.png')]
        next_idx = len(existing)

        # Add correction images with duplication
        added = 0
        for row, img_path in valid_rows:
            for dup in range(args.duplication):
                img_name = f"corr_{next_idx:06d}.png"
                lbl_name = f"corr_{next_idx:06d}.txt"
                shutil.copy2(img_path, os.path.join(new_images, img_name))
                with open(os.path.join(new_labels, lbl_name), 'w', encoding='utf-8') as f:
                    f.write(row.corrected_text)
                next_idx += 1
                added += 1

        # Also write a gt.txt (image_path\tlabel) for LMDB creation
        gt_path = os.path.join(new_train, 'gt.txt')
        with open(gt_path, 'w', encoding='utf-8') as gt_f:
            for fname in sorted(os.listdir(new_images)):
                if not fname.endswith('.png'):
                    continue
                lbl_file = os.path.join(new_labels, fname.replace('.png', '.txt'))
                if os.path.exists(lbl_file):
                    with open(lbl_file, 'r', encoding='utf-8') as lf:
                        label = lf.read().strip()
                    gt_f.write(f"images/{fname}\t{label}\n")

        print(f"Created {new_dir}")
        print(f"  Base training images: {len(existing)}")
        print(f"  Correction images added: {added}")
        print(f"  Total: {len(existing) + added}")

        # Update DB status
        for row, _ in valid_rows:
            row.status = 'trained'
            row.trained_version = args.new_version
        db.commit()
        print(f"Updated {len(valid_rows)} corrections to status='trained'")

    finally:
        db.close()


if __name__ == '__main__':
    main()
