#!/usr/bin/env python3
"""Training launcher for the header OCR model.

Dedicated to recognizing the 9 section header labels:
  등급, 아이템 속성, 인챈트, 개조, 세공, 에르그, 세트아이템, 정령, 아이템 색상

Key differences from the content OCR model (configs/training_config.yaml):
  - imgW: 128  (crops are 26-59px wide → 52-118px after height-scale to 32; no squash needed)
  - imgW: 200  would over-pad; 128 fits all header crops with no squashing
  - batch_max_length: 10  (longest label is 6 chars '아이템 색상', 10 gives headroom)
  - charset: 22 chars only (derived from the 9 labels)
  - num_iter: 10000  (small dataset, simple task)
  - valInterval: 500
  - checkpoints saved to: saved_models/header_ocr/

Usage (from project root):
    python3 scripts/train_header.py
    python3 scripts/train_header.py --resume
    python3 scripts/train_header.py --num_iter 5000
    python3 scripts/train_header.py --batch_size 16
"""

import argparse
import os
import subprocess
import sys

PROJECT_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_SCRIPT  = os.path.join(PROJECT_ROOT, 'deep-text-recognition-benchmark', 'train.py')
LMDB_DIR      = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'header_train_data_lmdb')
SAVED_DIR     = os.path.join(PROJECT_ROOT, 'saved_models', 'header_ocr')

# Header-specific charset: all unique characters across the 9 labels
HEADER_LABELS  = ['등급', '아이템 속성', '인챈트', '개조', '세공', '에르그', '세트아이템', '정령', '아이템 색상']
HEADER_CHARSET = ''.join(sorted(set(''.join(HEADER_LABELS))))  # 22 chars incl. space

# Header-specific model config
IMG_H             = 32
IMG_W             = 128   # fits 26-59px header crops scaled to h=32 without squashing
BATCH_MAX_LENGTH  = 10
BATCH_SIZE        = 32
NUM_ITER          = 10000
VAL_INTERVAL      = 500
WORKERS           = 0


def main():
    parser = argparse.ArgumentParser(description='Train header OCR model')
    parser.add_argument('--resume',      action='store_true', help='Continue from best checkpoint')
    parser.add_argument('--num_iter',    type=int, help='Override number of iterations')
    parser.add_argument('--batch_size',  type=int, help='Override batch size')
    parser.add_argument('--valInterval', type=int, help='Override validation interval')
    args = parser.parse_args()

    num_iter    = args.num_iter    or NUM_ITER
    batch_size  = args.batch_size  or BATCH_SIZE
    val_interval = args.valInterval or VAL_INTERVAL

    if not os.path.exists(TRAIN_SCRIPT):
        print(f"Error: {TRAIN_SCRIPT} not found")
        sys.exit(1)
    if not os.path.exists(LMDB_DIR):
        print(f"Error: LMDB not found at {LMDB_DIR}")
        print("Run: python3 scripts/create_header_lmdb.py")
        sys.exit(1)

    saved_model = ''
    if args.resume:
        best_path = os.path.join(SAVED_DIR, 'best_accuracy.pth')
        if os.path.exists(best_path):
            saved_model = best_path
            print(f"Resuming from: {saved_model}")
        else:
            print(f"Warning: --resume specified but {best_path} not found. Training from scratch.")

    cmd = [
        sys.executable, '-u', TRAIN_SCRIPT,
        '--train_data',       LMDB_DIR,
        '--valid_data',       LMDB_DIR,
        '--select_data',      '/',
        '--batch_ratio',      '1',
        '--Transformation',   'TPS',
        '--FeatureExtraction','ResNet',
        '--SequenceModeling', 'BiLSTM',
        '--Prediction',       'CTC',
        '--imgH',             str(IMG_H),
        '--imgW',             str(IMG_W),
        '--batch_max_length', str(BATCH_MAX_LENGTH),
        '--batch_size',       str(batch_size),
        '--num_iter',         str(num_iter),
        '--valInterval',      str(val_interval),
        '--workers',          str(WORKERS),
        '--character',        HEADER_CHARSET,
        '--saved_model',      saved_model,
        '--exp_name',         'header_ocr',
    ]
    cmd.append('--sensitive')
    cmd.append('--PAD')

    print('=' * 60)
    print('  Header OCR Training Launcher')
    print('=' * 60)
    print(f'  LMDB        : {LMDB_DIR}')
    print(f'  Saved models: {SAVED_DIR}')
    print()
    print(f'  imgH={IMG_H}, imgW={IMG_W}')
    print(f'  batch_max_length : {BATCH_MAX_LENGTH}')
    print(f'  batch_size       : {batch_size}')
    print(f'  num_iter         : {num_iter}')
    print(f'  valInterval      : {val_interval}')
    print(f'  charset ({len(HEADER_CHARSET)} chars): {HEADER_CHARSET!r}')
    print()
    print(f'  Command: {" ".join(cmd)}')
    print('=' * 60)
    print()

    subprocess.run(cmd, cwd=PROJECT_ROOT)


if __name__ == '__main__':
    main()
