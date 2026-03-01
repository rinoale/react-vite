"""Integration tests for shape walker + prefix detector on real tooltip images.

Verifies header detection, line detection, and prefix classification counts
against known ground truth values. Tests run on original color screenshots
and require no GPU — all operations are CPU-only (color masks, line splitting,
shape walking).

Skips automatically when sample images are not present (they are not committed
to git).
"""

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
_SAMPLE_DIR = os.path.join(_PROJECT_ROOT, 'data', 'sample_images')
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

_has_samples = os.path.isdir(_SAMPLE_DIR)
_has_config = os.path.isfile(_CONFIG_PATH)

skip_no_images = pytest.mark.skipif(
    not (_has_samples and _has_config),
    reason='Sample images or config not available',
)


def _image_path(name):
    return os.path.join(_SAMPLE_DIR, f'{name}_original.png')


def _skip_missing(name):
    path = _image_path(name)
    if not os.path.isfile(path):
        pytest.skip(f'{name}_original.png not found')
    return path


# ---------------------------------------------------------------------------
# Expected counts per image
#   (headers, bullet_lines, white_lines, bullets, subbullets)
#
# Active classifier: _classify_ink (width + vertical ink extent)
# To switch: change detect_prefix() in prefix_detector.py
#   _classify_ink:          width-based, fast, some false positive subbullets
#   _classify_shape_walker: shape tracing, precise, zero false positive subbullets
# ---------------------------------------------------------------------------

EXPECTED = {
    'captain_suit':           {'headers': 4,  'bullet_lines': 25,  'white_lines': 18,  'bullets': 2,   'subbullets': 0},
    'dropbell':               {'headers': 4,  'bullet_lines': 30,  'white_lines': 16,  'bullets': 13,  'subbullets': 1},
    'dualgun_abbrev':         {'headers': 12, 'bullet_lines': 38,  'white_lines': 19,  'bullets': 17,  'subbullets': 1},
    'dualgun':                {'headers': 9,  'bullet_lines': 53,  'white_lines': 30,  'bullets': 23,  'subbullets': 0},
    'enchant_scroll':         {'headers': 1,  'bullet_lines': 11,  'white_lines': 5,   'bullets': 3,   'subbullets': 0},
    'lightarmor':             {'headers': 7,  'bullet_lines': 75,  'white_lines': 45,  'bullets': 25,  'subbullets': 1},
    'lobe':                   {'headers': 2,  'bullet_lines': 32,  'white_lines': 31,  'bullets': 1,   'subbullets': 1},
    'plate_helmet':           {'headers': 6,  'bullet_lines': 38,  'white_lines': 23,  'bullets': 15,  'subbullets': 0},
    'plate_helmet_simple':    {'headers': 6,  'bullet_lines': 29,  'white_lines': 14,  'bullets': 15,  'subbullets': 0},
    'predator_ng':            {'headers': 8,  'bullet_lines': 69,  'white_lines': 39,  'bullets': 25,  'subbullets': 8},
    'predator_simple_fhd_cm': {'headers': 9,  'bullet_lines': 36,  'white_lines': 20,  'bullets': 17,  'subbullets': 0},
    'predator_simple_fhd_ng': {'headers': 10, 'bullet_lines': 33,  'white_lines': 16,  'bullets': 17,  'subbullets': 6},
    'shoes':                  {'headers': 6,  'bullet_lines': 37,  'white_lines': 26,  'bullets': 12,  'subbullets': 7},
    'soul_shield':            {'headers': 9,  'bullet_lines': 66,  'white_lines': 48,  'bullets': 18,  'subbullets': 2},
    'spellbook':              {'headers': 6,  'bullet_lines': 34,  'white_lines': 22,  'bullets': 9,   'subbullets': 6},
    'titan_blade':            {'headers': 8,  'bullet_lines': 72,  'white_lines': 39,  'bullets': 32,  'subbullets': 5},
    'wingshoes_abbrev':       {'headers': 6,  'bullet_lines': 30,  'white_lines': 15,  'bullets': 14,  'subbullets': 0},
    'wingshoes_detail':       {'headers': 6,  'bullet_lines': 37,  'white_lines': 22,  'bullets': 16,  'subbullets': 2},
}


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


def _run_full_analysis(name):
    """Run full header + line + prefix analysis on an image."""
    img, config = _load_image(name)
    h, w = img.shape[:2]

    headers = detect_headers(img, config)
    splitter = TooltipLineSplitter()

    b_mask = bullet_text_mask(img)
    w_mask = white_text_mask(img)
    bullet_lines = splitter.detect_text_lines(b_mask)
    white_lines = splitter.detect_text_lines(w_mask)

    bullets = _count_prefixes(b_mask, h, w, 'bullet')
    subs = _count_prefixes(w_mask, h, w, 'subbullet')

    return {
        'headers': len(headers),
        'bullet_lines': len(bullet_lines),
        'white_lines': len(white_lines),
        'bullets': bullets,
        'subbullets': subs,
    }


# ---------------------------------------------------------------------------
# Tests — parametrized over all images with expected counts
# ---------------------------------------------------------------------------

@skip_no_images
class TestHeaderDetection:
    """Verify orange header detection counts on real images."""

    @pytest.mark.parametrize('name', [
        'captain_suit', 'enchant_scroll', 'lobe',
        'plate_helmet_simple', 'dualgun_abbrev',
    ])
    def test_header_count(self, name):
        img, config = _load_image(name)
        headers = detect_headers(img, config)
        assert len(headers) == EXPECTED[name]['headers']


@skip_no_images
class TestLineDetection:
    """Verify text line detection counts on color masks."""

    @pytest.mark.parametrize('name', [
        'captain_suit', 'dropbell', 'enchant_scroll',
        'plate_helmet', 'shoes',
    ])
    def test_bullet_line_count(self, name):
        img, _ = _load_image(name)
        b_mask = bullet_text_mask(img)
        lines = TooltipLineSplitter().detect_text_lines(b_mask)
        assert len(lines) == EXPECTED[name]['bullet_lines']

    @pytest.mark.parametrize('name', [
        'captain_suit', 'dropbell', 'enchant_scroll',
        'plate_helmet', 'shoes',
    ])
    def test_white_line_count(self, name):
        img, _ = _load_image(name)
        w_mask = white_text_mask(img)
        lines = TooltipLineSplitter().detect_text_lines(w_mask)
        assert len(lines) == EXPECTED[name]['white_lines']


@skip_no_images
class TestPrefixDetection:
    """Verify bullet/subbullet prefix counts using shape walker."""

    @pytest.mark.parametrize('name', list(EXPECTED.keys()))
    def test_bullet_count(self, name):
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        b_mask = bullet_text_mask(img)
        bullets = _count_prefixes(b_mask, h, w, 'bullet')
        assert bullets == EXPECTED[name]['bullets']

    @pytest.mark.parametrize('name', list(EXPECTED.keys()))
    def test_subbullet_count(self, name):
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        w_mask = white_text_mask(img)
        subs = _count_prefixes(w_mask, h, w, 'subbullet')
        assert subs == EXPECTED[name]['subbullets']


@skip_no_images
@pytest.mark.skip(reason='Only valid when detect_prefix uses _classify_shape_walker')
class TestShapeWalkerConsistency:
    """Verify shape walker produces same results as detect_prefix on real data.

    Only valid when detect_prefix uses _classify_shape_walker internally.
    Skipped when _classify_ink is active (width-based classification disagrees
    with shape walker on some clusters).
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


@skip_no_images
class TestFullAnalysis:
    """End-to-end regression: all counts must match expected values."""

    @pytest.mark.parametrize('name', [
        'captain_suit', 'dualgun', 'lightarmor',
        'titan_blade', 'lobe',
    ])
    def test_all_counts(self, name):
        actual = _run_full_analysis(name)
        expected = EXPECTED[name]
        for key in expected:
            assert actual[key] == expected[key], (
                f'{name}.{key}: expected {expected[key]}, got {actual[key]}'
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

    @pytest.mark.parametrize('name', list(EXPECTED.keys()))
    def test_bullet_config_count(self, name):
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        b_mask = bullet_text_mask(img)
        bullets = _count_prefixes_with_config(b_mask, h, w, BULLET_DETECTOR)
        assert bullets == EXPECTED[name]['bullets']

    @pytest.mark.parametrize('name', list(EXPECTED.keys()))
    def test_subbullet_config_count(self, name):
        img, _ = _load_image(name)
        h, w = img.shape[:2]
        w_mask = white_text_mask(img)
        subs = _count_prefixes_with_config(w_mask, h, w, SUBBULLET_DETECTOR)
        assert subs == EXPECTED[name]['subbullets']
