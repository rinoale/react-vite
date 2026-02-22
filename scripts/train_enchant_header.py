#!/usr/bin/env python3
"""Training launcher for the enchant slot header OCR model.

Reads all parameters from configs/enchant_header_training_config.yaml.

Usage (from project root):
    python3 scripts/train_enchant_header.py
    python3 scripts/train_enchant_header.py --resume
    python3 scripts/train_enchant_header.py --num_iter 5000
    python3 scripts/train_enchant_header.py --batch_size 16
"""

import argparse
import os
import subprocess
import sys

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'enchant_header_training_config.yaml')
TRAIN_SCRIPT = os.path.join(PROJECT_ROOT, 'deep-text-recognition-benchmark', 'train.py')

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

model = cfg['model']
training = cfg['training']
paths = cfg['paths']

EXP_NAME = 'enchant_header_ocr'


def main():
    parser = argparse.ArgumentParser(description='Train enchant header OCR model')
    parser.add_argument('--resume', action='store_true', help='Continue from best checkpoint')
    parser.add_argument('--num_iter', type=int, help='Override number of iterations')
    parser.add_argument('--batch_size', type=int, help='Override batch size')
    parser.add_argument('--valInterval', type=int, help='Override validation interval')
    parser.add_argument('--adam', action='store_true', default=None,
                        help='Use Adam optimizer (default: from config)')
    parser.add_argument('--no-adam', action='store_true',
                        help='Force Adadelta optimizer, overriding config')
    parser.add_argument('--lr', type=float, help='Override learning rate')
    args = parser.parse_args()

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
        print("Run: python3 scripts/create_enchant_header_lmdb.py")
        sys.exit(1)

    with open(char_file, 'r', encoding='utf-8') as f:
        charset = f.read().replace('\n', '')

    saved_model = ''
    if args.resume:
        best_path = os.path.join(saved_dir, EXP_NAME, 'best_accuracy.pth')
        if os.path.exists(best_path):
            saved_model = best_path
            print(f"Resuming from: {saved_model}")
        else:
            print(f"Warning: --resume but {best_path} not found. Training from scratch.")

    cmd = [
        sys.executable, '-u', TRAIN_SCRIPT,
        '--train_data', lmdb_dir,
        '--valid_data', lmdb_dir,
        '--select_data', '/',
        '--batch_ratio', '1',
        '--Transformation', model['Transformation'],
        '--FeatureExtraction', model['FeatureExtraction'],
        '--SequenceModeling', model['SequenceModeling'],
        '--Prediction', model['Prediction'],
        '--imgH', str(model['imgH']),
        '--imgW', str(model['imgW']),
        '--batch_max_length', str(training['batch_max_length']),
        '--batch_size', str(batch_size),
        '--num_iter', str(num_iter),
        '--valInterval', str(val_interval),
        '--workers', str(training['workers']),
        '--character', charset,
        '--saved_model', saved_model,
        '--exp_name', EXP_NAME,
    ]
    if training.get('sensitive'):
        cmd.append('--sensitive')
    if training.get('PAD'):
        cmd.append('--PAD')
    # Optimizer: CLI --adam / --no-adam override config; config is default.
    # Adadelta (default in train.py) fails to converge on NanumGothicBold —
    # 0% accuracy after 10k iters. Adam with lr=0.001 reaches 99.8%.
    use_adam = training.get('adam', False)
    if args.adam:
        use_adam = True
    elif args.no_adam:
        use_adam = False
    if use_adam:
        cmd.append('--adam')

    # Learning rate: CLI --lr overrides config value.
    lr = args.lr if args.lr is not None else training.get('lr')
    if lr is not None:
        cmd.extend(['--lr', str(lr)])

    print('=' * 60)
    print('  Enchant Header OCR Training Launcher')
    print('=' * 60)
    print(f'  Config    : {CONFIG_PATH}')
    print(f'  LMDB      : {lmdb_dir}')
    print(f'  Saved dir : {saved_dir}/{EXP_NAME}')
    print()
    print(f'  imgH={model["imgH"]}, imgW={model["imgW"]}')
    print(f'  batch_max_length : {training["batch_max_length"]}')
    print(f'  batch_size       : {batch_size}')
    print(f'  num_iter         : {num_iter}')
    print(f'  valInterval      : {val_interval}')
    print(f'  optimizer        : {"Adam" if use_adam else "Adadelta"}')
    if lr is not None:
        print(f'  lr               : {lr}')
    print(f'  charset ({len(charset)} chars)')
    print()
    print(f'  Command: {" ".join(cmd)}')
    print('=' * 60)
    print()

    subprocess.run(cmd, cwd=PROJECT_ROOT)


if __name__ == '__main__':
    main()
