#!/usr/bin/env python3
"""
Generate custom_mabinogi.yaml for EasyOCR inference.

Reads model architecture params from the version's training_config.yaml
and character list from unique_chars.txt.

Run from project root:
    python3 scripts/ocr/general_model/create_model_config.py              # active version
    python3 scripts/ocr/general_model/create_model_config.py --version a19
"""
import argparse
import os
import sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config

parser = argparse.ArgumentParser(description='Generate EasyOCR inference yaml')
parser.add_argument('--version', default=None, help='Model version (default: active symlink)')
args = parser.parse_args()

version = resolve_version('general', args.version)
cfg = load_training_config('general', version)

model = cfg["model"]
inference = cfg["inference"]
paths = cfg["paths"]

# Read characters — do NOT use .strip() as space ' ' is a valid class
with open(paths["character_file"], "r", encoding="utf-8") as f:
    chars = f.read().replace('\n', '')

config = {
    'network_params': {
        'input_channel': model['input_channel'],
        'output_channel': model['output_channel'],
        'hidden_size': model['hidden_size'],
        'Transformation': model['Transformation'],
        'FeatureExtraction': model['FeatureExtraction'],
        'SequenceModeling': model['SequenceModeling'],
        'Prediction': model['Prediction'],
        'num_fiducial': model['num_fiducial'],
        'imgH': model['imgH'],
        'imgW': model['imgW'],
    },
    'imgH': model['imgH'],
    'imgW': model['imgW'],
    'lang_list': inference['lang_list'],
    'character_list': chars,
    'rgb': inference['rgb'],
    'PAD': cfg['training']['PAD'],
}

output_path = paths["training_model_config"]

os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    yaml.dump(config, f, allow_unicode=True)

print(f"Version: {version}")
print(f"Created {output_path}")
print(f"  imgH={model['imgH']}, imgW={model['imgW']}")
print(f"  characters: {len(chars)} chars")
print()
print(f"Production yaml NOT updated. Deploy with:")
print(f"  bash scripts/ocr/general_model/deploy.sh {version}")
