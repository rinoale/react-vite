"""Central path constants for the project.

Import from anywhere:
    from core.paths import BACKEND_DIR, PROJECT_DIR, DATA_DIR, ...
"""
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)

# Key directories
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
CONFIGS_DIR = os.path.join(PROJECT_DIR, 'configs')
DICT_DIR = os.path.join(DATA_DIR, 'dictionary')
TMP_DIR = os.path.join(PROJECT_DIR, 'tmp')
LOGS_DIR = os.path.join(PROJECT_DIR, 'logs')

# OCR
MODELS_DIR = os.path.join(BACKEND_DIR, 'ocr', 'models')
OCR_CROPS_DIR = os.path.join(TMP_DIR, 'ocr_crops')
CORRECTIONS_DIR = os.path.join(DATA_DIR, 'corrections')
