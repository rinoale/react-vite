"""Integration tests for shape walker + prefix detector on real tooltip images.

Verifies header detection, line detection, and prefix classification counts
against ground truth values stored in .meta.json files alongside sample images.

Tests run on original color screenshots and require no GPU — all operations
are CPU-only (color masks, line splitting, shape walking).

Skips automatically when sample images are not present (they are not committed
to git).
"""

import json
import os

import cv2
import numpy as np
import pytest

from lib.prefix_detector import (
    bullet_text_mask,
    white_text_mask,
    detect_prefix,
    BULLET_DETECTOR,
    SUBBULLET_DETECTOR,
)
from lib.shape_walker import classify_cluster, SHAPE_NIEUN, SHAPE_DOT
from lib.tooltip_line_splitter import TooltipLineSplitter
from lib.tooltip_segmenter import detect_headers, load_config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

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


def _skip_missing(name):
    path = _image_path(name)
    if not os.path.isfile(path):
        pytest.skip(f'{name}_original.png not found')
    return path


def _load_meta(name):
    """Load expected counts from .meta.json file."""
    path = _meta_path(name)
    if not os.path.isfile(path):
        pytest.skip(f'{name}_original.meta.json not found')
    with open(path) as f:
        return json.load(f)


def _all_image_names():
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


IMAGE_NAMES = _all_image_names()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_image(name):
    """Load image and return (img_bgr, config)."""
    path = _skip_missing(name)
    img = cv2.imread(path)
    assert img is not None, f'Failed to read {path}'
    config = load_config(_CONFIG_PATH)
    return img, config


def _count_prefixes(mask, img_h, img_w, target_type):
    """Count prefixes of target_type using detect_prefix on each detected line."""
    splitter = TooltipLineSplitter()
    lines = splitter.detect_text_lines(mask)
    count = 0
    for line in lines:
        x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
        pad_x = max(2, lh // 3)
        pad_y = max(1, lh // 5)
        y0 = max(0, y - pad_y)
        y1 = min(img_h, y + lh + pad_y)
        x0 = max(0, x - pad_x)
        x1 = min(img_w, x + lw + pad_x)
        line_mask = mask[y0:y1, x0:x1]
        info = detect_prefix(line_mask)
        if info['type'] == target_type:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Tests — parametrized over all images with expected counts
# ---------------------------------------------------------------------------

@skip_no_images
class TestHeaderDetection:
    """Verify orange header detection counts on real images."""

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_header_count(self, name):
        meta = _load_meta(name)
        img, config = _load_image(name)
        headers = detect_headers(img, config)
        assert len(headers) == meta['lines']['headers']


@skip_no_images
class TestLineDetection:
    """Verify text line detection counts on color masks."""

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_line_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        b_mask = bullet_text_mask(img)
        lines = TooltipLineSplitter().detect_text_lines(b_mask)
        assert len(lines) == meta['lines']['bullet_lines']

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_white_line_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        w_mask = white_text_mask(img)
        lines = TooltipLineSplitter().detect_text_lines(w_mask)
        assert len(lines) == meta['lines']['white_lines']


@skip_no_images
class TestPrefixDetection:
    """Verify bullet/subbullet prefix counts using shape walker."""

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        b_mask = bullet_text_mask(img)
        bullets = _count_prefixes(b_mask, h, w, 'bullet')
        assert bullets == meta['prefix']['bullets']

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_subbullet_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        w_mask = white_text_mask(img)
        subs = _count_prefixes(w_mask, h, w, 'subbullet')
        assert subs == meta['prefix']['subbullets']


@skip_no_images
class TestShapeWalkerConsistency:
    """Verify classify_cluster gives same result as detect_prefix on real data.

    Both use shape walker internally, so results must always agree.
    """

    @pytest.mark.parametrize('name', [
        'captain_suit', 'dropbell', 'plate_helmet_simple',
        'dualgun', 'titan_blade',
    ])
    def test_direct_classify_matches_detect_prefix(self, name):
        """classify_cluster called directly on extracted cluster gives same
        result as detect_prefix."""
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        b_mask = bullet_text_mask(img)
        splitter = TooltipLineSplitter()
        lines = splitter.detect_text_lines(b_mask)

        for line in lines:
            x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
            pad_x = max(2, lh // 3)
            pad_y = max(1, lh // 5)
            y0 = max(0, y - pad_y)
            y1 = min(h, y + lh + pad_y)
            x0 = max(0, x - pad_x)
            x1 = min(w, x + lw + pad_x)
            line_mask = b_mask[y0:y1, x0:x1]

            info = detect_prefix(line_mask)
            if info['type'] is None:
                continue

            # Extract the same cluster region detect_prefix uses
            cluster_region = line_mask[:, info['x']:info['x'] + info['w']]
            match = classify_cluster(cluster_region, [SHAPE_NIEUN, SHAPE_DOT])

            assert match is not None, (
                f'{name}: detect_prefix found {info["type"]} at y={y} but '
                f'classify_cluster returned None on the cluster region'
            )

            expected_type = 'subbullet' if match.shape.name == 'ㄴ' else 'bullet'
            assert expected_type == info['type'], (
                f'{name}: mismatch at y={y}: '
                f'detect_prefix={info["type"]}, classify_cluster={match.shape.name}'
            )


def _count_prefixes_with_config(mask, img_h, img_w, config):
    """Count prefixes using a PrefixDetectorConfig on each detected line."""
    splitter = TooltipLineSplitter()
    lines = splitter.detect_text_lines(mask)
    count = 0
    for line in lines:
        x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
        pad_x = max(2, lh // 3)
        pad_y = max(1, lh // 5)
        y0 = max(0, y - pad_y)
        y1 = min(img_h, y + lh + pad_y)
        x0 = max(0, x - pad_x)
        x1 = min(img_w, x + lw + pad_x)
        line_mask = mask[y0:y1, x0:x1]
        info = detect_prefix(line_mask, config=config)
        if info['type'] is not None:
            count += 1
    return count


@skip_no_images
class TestConfigBasedDetection:
    """Verify config-based classification matches backward-compat counts.

    Uses the same masks as existing tests (bullet_text_mask / white_text_mask)
    so line detection is identical. Only the classification path differs:
    config restricts which shapes are tried (DOT-only for bullet, NIEUN-only
    for subbullet) vs backward-compat which tries both.
    """

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_config_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        b_mask = bullet_text_mask(img)
        bullets = _count_prefixes_with_config(b_mask, h, w, BULLET_DETECTOR)
        assert bullets == meta['prefix']['bullets']

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_subbullet_config_count(self, name):
        meta = _load_meta(name)
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        w_mask = white_text_mask(img)
        subs = _count_prefixes_with_config(w_mask, h, w, SUBBULLET_DETECTOR)
        assert subs == meta['prefix']['subbullets']
