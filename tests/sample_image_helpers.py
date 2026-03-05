"""Shared helpers for tests that use real sample images.

Provides image discovery, loading, border cropping, and meta.json loading.
Used by test_line_splitter.py, test_prefix_detector.py, and
test_finding_bullet_images.py.
"""

import json
import os

import cv2
import pytest

from lib.pipeline.segmenter import (
    detect_bottom_border, detect_vertical_borders, load_config,
)

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'sample_images')
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

_has_samples = os.path.isdir(_SAMPLE_DIR)
_has_config = os.path.isfile(_CONFIG_PATH)

skip_no_images = pytest.mark.skipif(
    not (_has_samples and _has_config),
    reason='Sample images or config not available',
)


def _image_path(name):
    return os.path.join(_SAMPLE_DIR, f'{name}_original.png')


def _meta_path(name):
    return os.path.join(_SAMPLE_DIR, f'{name}_original.meta.json')


def discover_image_names():
    """Discover all images that have both .png and .meta.json files."""
    if not _has_samples:
        return []
    names = []
    for fname in sorted(os.listdir(_SAMPLE_DIR)):
        if fname.endswith('_original.meta.json'):
            name = fname.replace('_original.meta.json', '')
            if os.path.isfile(_image_path(name)):
                names.append(name)
    return names


IMAGE_NAMES = discover_image_names()


def crop_tooltip_border(img):
    """Crop to tooltip boundary (same as V3 pipeline Stage 1)."""
    bottom_y = detect_bottom_border(img)
    left_x, right_x = detect_vertical_borders(img)
    y1 = (bottom_y + 1) if bottom_y is not None else img.shape[0]
    x0 = (left_x + 1) if left_x is not None else 0
    x1 = right_x if right_x is not None else img.shape[1]
    return img[0:y1, x0:x1]


def load_sample_image(name):
    """Load image cropped to tooltip boundary, return (img_bgr, config).

    Skips if image file is missing.
    """
    path = _image_path(name)
    if not os.path.isfile(path):
        pytest.skip(f'{name}_original.png not found')
    img = cv2.imread(path)
    assert img is not None, f'Failed to read {path}'
    img = crop_tooltip_border(img)
    config = load_config(_CONFIG_PATH)
    return img, config


def load_sample_meta(name):
    """Load expected counts from .meta.json file.

    Skips if meta file is missing.
    """
    path = _meta_path(name)
    if not os.path.isfile(path):
        pytest.skip(f'{name}_original.meta.json not found')
    with open(path) as f:
        return json.load(f)
