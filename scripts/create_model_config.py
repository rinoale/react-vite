import yaml

# Read characters
with open("backend/unique_chars.txt", "r", encoding="utf-8") as f:
    # Do NOT use .strip() as it removes the space character ' ' which is a valid class
    chars = f.read().replace('\n', '')

    config = {
    'network_params': {
        'input_channel': 1,
        'output_channel': 512,
        'hidden_size': 256,
        'Transformation': 'TPS',
        'FeatureExtraction': 'ResNet',
        'SequenceModeling': 'BiLSTM',
        'Prediction': 'CTC',
        'num_fiducial': 20,
        'imgH': 32,
        'imgW': 200,
    },
    'imgH': 32,
    'imgW': 200,
    'lang_list': ['ko'],
    'character_list': chars,
    'rgb': False,
    'PAD': True
}

with open("backend/models/custom_mabinogi.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config, f, allow_unicode=True)

print("Created backend/models/custom_mabinogi.yaml")
