#!/usr/bin/env python3
"""
Generate custom_mabinogi.yaml for EasyOCR inference.

Reads model architecture params from training_config.yaml (single source of truth)
and character list from unique_chars.txt.

Run from project root:
    python3 scripts/create_model_config.py
"""
import yaml

# Load training config (single source of truth for architecture params)
with open("configs/training_config.yaml", "r", encoding="utf-8") as f:
    training_cfg = yaml.safe_load(f)

model = training_cfg["model"]
inference = training_cfg["inference"]
paths = training_cfg["paths"]

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
    'PAD': training_cfg['training']['PAD'],
}

output_path = paths["model_config"]
with open(output_path, "w", encoding="utf-8") as f:
    yaml.dump(config, f, allow_unicode=True)

print(f"Created {output_path}")
print(f"  imgH={model['imgH']}, imgW={model['imgW']}")
print(f"  characters: {len(chars)} chars")
