#!/usr/bin/env python3
"""Training launcher for the category header OCR model.

Dedicated to recognizing the 9 section header labels:
  등급, 아이템 속성, 인챈트, 개조, 세공, 에르그, 세트아이템, 정령, 아이템 색상

Usage (from project root):
    python3 scripts/ocr/category_header_model/train.py
    python3 scripts/ocr/category_header_model/train.py --version v2
    python3 scripts/ocr/category_header_model/train.py --resume
    python3 scripts/ocr/category_header_model/train.py --num_iter 5000
    python3 scripts/ocr/category_header_model/train.py --batch_size 16
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config, training_config_path, PROJECT_ROOT
TRAIN_SCRIPT = os.path.join(PROJECT_ROOT, 'deep-text-recognition-benchmark', 'train.py')


def main():
    parser = argparse.ArgumentParser(description='Train category header OCR model')
    parser.add_argument('--version',     default=None, help='Model version (default: active symlink)')
    parser.add_argument('--resume',      action='store_true', help='Continue from best checkpoint')
    parser.add_argument('--resume-from', default=None, metavar='VERSION',
                        help="Resume from a different version's checkpoint (e.g. --resume-from v1)")
    parser.add_argument('--num_iter',    type=int, help='Override number of iterations')
    parser.add_argument('--batch_size',  type=int, help='Override batch size')
    parser.add_argument('--valInterval', type=int, help='Override validation interval')
    args = parser.parse_args()

    version = resolve_version('category_header', args.version)
    config_path = training_config_path('category_header', version)
    cfg = load_training_config('category_header', version)

    model = cfg['model']
    training = cfg['training']
    paths = cfg['paths']
    exp_name_prefix = training.get('exp_name', 'header_ocr')
    exp_name = f'{exp_name_prefix}_{version}'

    num_iter = args.num_iter or training['num_iter']
    batch_size = args.batch_size or training['batch_size']
    val_interval = args.valInterval or training['valInterval']

    lmdb_dir = os.path.join(PROJECT_ROOT, paths['train_data'])
    char_file = os.path.join(PROJECT_ROOT, paths['character_file'])
    saved_dir = os.path.join(PROJECT_ROOT, paths['saved_models_dir'])

    if not os.path.exists(TRAIN_SCRIPT):
        print(f"Error: {TRAIN_SCRIPT} not found")
        sys.exit(1)
    if not os.path.exists(lmdb_dir):
        print(f"Error: LMDB not found at {lmdb_dir}")
        print("Run: python3 scripts/ocr/category_header_model/create_lmdb.py")
        sys.exit(1)

    with open(char_file, 'r', encoding='utf-8') as f:
        charset = f.read().replace('\n', '')

    saved_model = ''
    if args.resume_from:
        source_exp = f'{exp_name_prefix}_{args.resume_from}'
        best_path = os.path.join(saved_dir, source_exp, 'best_accuracy.pth')
        if os.path.exists(best_path):
            saved_model = best_path
            print(f"Resuming from {args.resume_from}: {saved_model}")
        else:
            print(f"Error: --resume-from {args.resume_from} but {best_path} not found.")
            sys.exit(1)
    elif args.resume:
        best_path = os.path.join(saved_dir, exp_name, 'best_accuracy.pth')
        if os.path.exists(best_path):
            saved_model = best_path
            print(f"Resuming from: {saved_model}")
        else:
            print(f"Warning: --resume specified but {best_path} not found. Training from scratch.")

    cmd = [
        sys.executable, '-u', TRAIN_SCRIPT,
        '--train_data',       lmdb_dir,
        '--valid_data',       lmdb_dir,
        '--select_data',      '/',
        '--batch_ratio',      '1',
        '--Transformation',   model['Transformation'],
        '--FeatureExtraction', model['FeatureExtraction'],
        '--SequenceModeling', model['SequenceModeling'],
        '--Prediction',       model['Prediction'],
        '--imgH',             str(model['imgH']),
        '--imgW',             str(model['imgW']),
        '--batch_max_length', str(training['batch_max_length']),
        '--batch_size',       str(batch_size),
        '--num_iter',         str(num_iter),
        '--valInterval',      str(val_interval),
        '--workers',          str(training['workers']),
        '--character',        charset,
        '--saved_model',      saved_model,
        '--exp_name',         exp_name,
    ]
    if training.get('sensitive'):
        cmd.append('--sensitive')
    if training.get('PAD'):
        cmd.append('--PAD')

    print('=' * 60)
    print('  Category Header OCR Training Launcher')
    print('=' * 60)
    print(f'  Version   : {version}')
    print(f'  Config    : {config_path}')
    print(f'  LMDB      : {lmdb_dir}')
    print(f'  Saved dir : {saved_dir}/{exp_name}')
    print()
    print(f'  imgH={model["imgH"]}, imgW={model["imgW"]}')
    print(f'  batch_max_length : {training["batch_max_length"]}')
    print(f'  batch_size       : {batch_size}')
    print(f'  num_iter         : {num_iter}')
    print(f'  valInterval      : {val_interval}')
    print(f'  charset ({len(charset)} chars): {charset!r}')
    print()
    print(f'  Command: {" ".join(cmd)}')
    print('=' * 60)
    print()

    subprocess.run(cmd, cwd=PROJECT_ROOT)


if __name__ == '__main__':
    main()
