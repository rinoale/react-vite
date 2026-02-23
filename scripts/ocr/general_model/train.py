#!/usr/bin/env python3
"""
Training launcher — reads training_config.yaml from the version folder and runs train.py.

Usage (from project root):
    python3 scripts/ocr/general_model/train.py                          # Train active version
    python3 scripts/ocr/general_model/train.py --version a19            # Train specific version
    python3 scripts/ocr/general_model/train.py --resume                 # Continue from best checkpoint
    python3 scripts/ocr/general_model/train.py --saved_model path.pth   # Continue from specific checkpoint
    python3 scripts/ocr/general_model/train.py --num_iter 20000         # Override iterations
    python3 scripts/ocr/general_model/train.py --batch_size 32          # Override batch size (e.g. OOM)

Any flag passed on the command line overrides the config file value.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config, training_config_path

TRAIN_SCRIPT = "deep-text-recognition-benchmark/train.py"


def load_characters(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().replace("\n", "")


def build_command(cfg, overrides):
    model = cfg["model"]
    training = cfg["training"]
    paths = cfg["paths"]

    characters = load_characters(paths["character_file"])

    # Apply overrides
    if overrides.num_iter is not None:
        training["num_iter"] = overrides.num_iter
    if overrides.batch_size is not None:
        training["batch_size"] = overrides.batch_size
    if overrides.valInterval is not None:
        training["valInterval"] = overrides.valInterval

    # Determine saved_model
    saved_model = ""
    if overrides.resume:
        # Find best_accuracy.pth in saved_models dir
        seed_dir = os.path.join(paths["saved_models_dir"], "TPS-ResNet-BiLSTM-CTC-Seed1111")
        best_path = os.path.join(seed_dir, "best_accuracy.pth")
        if os.path.exists(best_path):
            saved_model = best_path
            print(f"Resuming from: {saved_model}")
        else:
            print(f"Warning: --resume specified but {best_path} not found. Training from scratch.")
    elif overrides.saved_model:
        saved_model = overrides.saved_model

    cmd = [
        sys.executable, "-u", TRAIN_SCRIPT,
        "--train_data", paths["train_data"],
        "--valid_data", paths["valid_data"],
        "--select_data", "/",
        "--batch_ratio", "1",
        "--Transformation", model["Transformation"],
        "--FeatureExtraction", model["FeatureExtraction"],
        "--SequenceModeling", model["SequenceModeling"],
        "--Prediction", model["Prediction"],
        "--imgH", str(model["imgH"]),
        "--imgW", str(model["imgW"]),
        "--batch_max_length", str(training["batch_max_length"]),
        "--batch_size", str(training["batch_size"]),
        "--num_iter", str(training["num_iter"]),
        "--valInterval", str(training["valInterval"]),
        "--workers", str(training["workers"]),
        "--character", characters,
        "--saved_model", saved_model,
    ]

    if training.get("sensitive"):
        cmd.append("--sensitive")
    if training.get("PAD"):
        cmd.append("--PAD")

    return cmd


def main():
    parser = argparse.ArgumentParser(description="Train general OCR model")
    parser.add_argument("--version", type=str, default=None, help="Model version (default: active symlink)")
    parser.add_argument("--resume", action="store_true", help="Continue from best checkpoint")
    parser.add_argument("--saved_model", type=str, help="Path to specific checkpoint to resume from")
    parser.add_argument("--num_iter", type=int, help="Override number of iterations")
    parser.add_argument("--batch_size", type=int, help="Override batch size")
    parser.add_argument("--valInterval", type=int, help="Override validation interval")
    overrides = parser.parse_args()

    version = resolve_version('general', overrides.version)
    config_path = training_config_path('general', version)

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    if not os.path.exists(TRAIN_SCRIPT):
        print(f"Error: Training script not found at {TRAIN_SCRIPT}")
        sys.exit(1)

    cfg = load_training_config('general', version)
    cmd = build_command(cfg, overrides)

    model = cfg["model"]
    training = cfg["training"]
    paths = cfg["paths"]

    print("=" * 60)
    print("  OCR Training Launcher")
    print("=" * 60)
    print(f"  Version   : {version}")
    print(f"  Config    : {config_path}")
    print(f"  Train script: {TRAIN_SCRIPT}")
    print()
    print("  [Model Architecture]")
    print(f"    Transformation : {model['Transformation']}")
    print(f"    FeatureExtract : {model['FeatureExtraction']}")
    print(f"    SequenceModel  : {model['SequenceModeling']}")
    print(f"    Prediction     : {model['Prediction']}")
    print(f"    imgH={model['imgH']}, imgW={model['imgW']}")
    print()
    print("  [Training Params]")
    print(f"    batch_size     : {training['batch_size']}")
    print(f"    num_iter       : {training['num_iter']}")
    print(f"    valInterval    : {training['valInterval']}")
    print(f"    batch_max_len  : {training['batch_max_length']}")
    print(f"    sensitive      : {training.get('sensitive', False)}")
    print(f"    PAD            : {training.get('PAD', False)}")
    print(f"    workers        : {training['workers']}")
    print()
    print("  [Data Paths]")
    print(f"    train_data     : {paths['train_data']}")
    print(f"    valid_data     : {paths['valid_data']}")
    print(f"    character_file : {paths['character_file']}")
    print(f"    saved_model    : {cmd[cmd.index('--saved_model') + 1] or '(from scratch)'}")
    print()
    print("  [Full Command]")
    print(f"  {' '.join(cmd)}")
    print("=" * 60)
    print()

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
