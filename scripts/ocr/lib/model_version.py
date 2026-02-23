"""Resolve OCR model version and training config path.

Model types and their layout under backend/ocr/:
  general          → general_model/{version}/training_config.yaml
  enchant_header   → enchant_header_model/{version}/training_config.yaml
  category_header  → category_header_model/{version}/training_config.yaml

When --version is not specified, the active version is detected from the
symlink target in backend/ocr/models/.
"""

import os
import yaml

# scripts/ocr/lib/model_version.py → 4 levels up to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Map model type → (version_dir_prefix, symlink_file_to_probe)
_MODEL_TYPES = {
    'general': ('general_model', 'custom_mabinogi.pth'),
    'enchant_header': ('enchant_header_model', 'custom_enchant_header.pth'),
    'category_header': ('category_header_model', 'custom_header.pth'),
}


def active_version(model_type: str) -> str:
    """Detect the active version from the symlink in backend/ocr/models/."""
    _, probe = _MODEL_TYPES[model_type]
    link = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models', probe)
    if not os.path.islink(link):
        raise RuntimeError(f'{link} is not a symlink — cannot detect active version')
    # e.g. ../general_model/a18/custom_mabinogi.pth → extract 'a18'
    target = os.readlink(link)
    parts = target.replace('\\', '/').split('/')
    # parts like ['..', 'general_model', 'a18', 'custom_mabinogi.pth']
    return parts[-2]


def version_dir(model_type: str, version: str) -> str:
    """Return absolute path to a version folder."""
    prefix, _ = _MODEL_TYPES[model_type]
    return os.path.join(PROJECT_ROOT, 'backend', 'ocr', prefix, version)


def training_config_path(model_type: str, version: str) -> str:
    """Return absolute path to the training config for a given version."""
    return os.path.join(version_dir(model_type, version), 'training_config.yaml')


def load_training_config(model_type: str, version: str) -> dict:
    """Load and return the training config dict for a given model type + version."""
    path = training_config_path(model_type, version)
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Training config not found: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def resolve_version(model_type: str, version_arg: str | None) -> str:
    """Return explicit version if given, otherwise detect from symlink."""
    if version_arg:
        return version_arg
    return active_version(model_type)
