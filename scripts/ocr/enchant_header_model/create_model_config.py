#!/usr/bin/env python3
"""Generate custom_enchant_header.yaml for EasyOCR inference.

Reads model architecture params from the version's training_config.yaml
and character list from enchant_header_chars.txt.

Run from project root:
    python3 scripts/ocr/enchant_header_model/create_model_config.py              # active version
    python3 scripts/ocr/enchant_header_model/create_model_config.py --version v2
"""
import argparse
import os
import sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config

parser = argparse.ArgumentParser(description='Generate enchant header EasyOCR inference yaml')
parser.add_argument('--version', default=None, help='Model version (default: active symlink)')
args = parser.parse_args()

version = resolve_version('enchant_header', args.version)
cfg = load_training_config('enchant_header', version)

model = cfg["model"]
inference = cfg["inference"]
paths = cfg["paths"]

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

output_path = paths["model_config"]
with open(output_path, "w", encoding="utf-8") as f:
    yaml.dump(config, f, allow_unicode=True)

print(f"Version: {version}")
print(f"Created {output_path}")
print(f"  imgH={model['imgH']}, imgW={model['imgW']}")
print(f"  characters: {len(chars)} chars")
