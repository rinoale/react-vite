#!/usr/bin/env python3
"""Generate custom_enchant_header.yaml for EasyOCR inference.

Reads model architecture params from enchant_header_training_config.yaml
and character list from enchant_header_chars.txt.

Run from project root:
    python3 scripts/create_enchant_header_model_config.py
"""
import yaml

CONFIG_PATH = "configs/enchant_header_training_config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

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

print(f"Created {output_path}")
print(f"  imgH={model['imgH']}, imgW={model['imgW']}")
print(f"  characters: {len(chars)} chars")
