#!/usr/bin/env python3
"""Prepare header OCR training data and create LMDB dataset.

Reads data/sample_headers/labels.txt (format: filename<TAB>label),
copies processed images into backend/ocr/header_train_data/images/,
writes individual label files to backend/ocr/header_train_data/labels/,
then creates the LMDB at backend/ocr/header_train_data_lmdb/.

Usage:
    python3 scripts/create_header_lmdb.py
"""

import os
import shutil
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_DIR    = os.path.join(PROJECT_ROOT, 'data', 'sample_headers')
LABELS_TXT = os.path.join(SRC_DIR, 'labels.txt')
DATA_DIR   = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'header_train_data')
LMDB_DIR   = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'header_train_data_lmdb')
LMDB_SCRIPT = os.path.join(PROJECT_ROOT, 'skills', 'ocr-trainer', 'scripts', 'create_lmdb_dataset.py')

IMG_DIR   = os.path.join(DATA_DIR, 'images')
LABEL_DIR = os.path.join(DATA_DIR, 'labels')


def main():
    if not os.path.isfile(LABELS_TXT):
        print(f"Error: {LABELS_TXT} not found. Run GT creation first.")
        sys.exit(1)

    # Read labels.txt
    entries = []
    with open(LABELS_TXT, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) != 2:
                print(f"Warning: malformed line: {line!r}")
                continue
            filename, label = parts
            entries.append((filename, label))

    print(f"Loaded {len(entries)} GT entries from {LABELS_TXT}")

    # Clear and recreate output dirs
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    os.makedirs(IMG_DIR)
    os.makedirs(LABEL_DIR)

    copied = 0
    skipped = 0
    for filename, label in entries:
        src_img = os.path.join(SRC_DIR, filename)
        if not os.path.isfile(src_img):
            print(f"Warning: image not found: {src_img}")
            skipped += 1
            continue

        # Copy image
        dst_img = os.path.join(IMG_DIR, filename)
        shutil.copy2(src_img, dst_img)

        # Write individual label file
        base = os.path.splitext(filename)[0]
        label_path = os.path.join(LABEL_DIR, base + '.txt')
        with open(label_path, 'w', encoding='utf-8') as f:
            f.write(label)

        copied += 1

    print(f"Prepared {copied} samples ({skipped} skipped) in {DATA_DIR}")

    # Show label distribution
    from collections import Counter
    counts = Counter(label for _, label in entries)
    print("Label distribution:")
    for label, count in sorted(counts.items()):
        print(f"  '{label}': {count}")

    # Create LMDB
    print(f"\nCreating LMDB at {LMDB_DIR} ...")
    import subprocess
    result = subprocess.run(
        [sys.executable, LMDB_SCRIPT, '--input', DATA_DIR, '--output', LMDB_DIR],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print("Error: LMDB creation failed.")
        sys.exit(1)
    print("Done.")


if __name__ == '__main__':
    main()
