"""Integration tests for shape walker + prefix detector on real tooltip images.

Verifies header detection, line detection, and prefix classification counts
against ground truth values stored in .meta.json files alongside sample images.

Tests run on original color screenshots and require no GPU — all operations
are CPU-only (color masks, line splitting, shape walking).

Skips automatically when sample images are not present (they are not committed
to git).
"""

import pytest

from lib.image_processors.prefix_detector import (
    bullet_text_mask,
    white_text_mask,
    detect_prefix_per_color,
    BULLET_DETECTOR,
    SUBBULLET_DETECTOR,
)
from lib.image_processors.shape_walker import classify_cluster, SHAPE_NIEUN, SHAPE_DOT
from lib.pipeline.line_split import MabinogiTooltipSplitter
from lib.pipeline.segmenter import detect_headers

from sample_image_helpers import (
    IMAGE_NAMES, skip_no_images, load_sample_image, load_sample_meta,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_prefixes_per_color(img_bgr, config):
    """Count prefixes using detect_prefix_per_color on BGR crops.

    Mirrors the production path: build color mask for line detection,
    then call detect_prefix_per_color(bgr_crop, config) per line.
    This is the same call that mabinogi_tooltip_parser._ocr_grouped_lines()
    and line_processing.promote_grey_by_prefix() use.
    """
    h, w = img_bgr.shape[:2]
    mask = config.build_mask(img_bgr)
    splitter = MabinogiTooltipSplitter()
    lines = splitter.detect_centered_lines(mask)
    count = 0
    for line in lines:
        x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
        pad_x = max(2, lh // 3)
        x0 = max(0, x - pad_x)
        x1 = min(w, x + lw + pad_x)
        bgr_crop = img_bgr[y:y + lh, x0:x1]
        info = detect_prefix_per_color(bgr_crop, config=config)
        if info['type'] is not None:
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
        meta = load_sample_meta(name)
        img, config = load_sample_image(name)
        headers = detect_headers(img, config)
        assert len(headers) == meta['lines']['headers']


@skip_no_images
class TestLineDetection:
    """Verify text line detection counts on color masks."""

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_line_count(self, name):
        meta = load_sample_meta(name)
        img, _ = load_sample_image(name)
        b_mask = bullet_text_mask(img)
        lines = MabinogiTooltipSplitter().detect_centered_lines(b_mask)
        assert len(lines) == meta['lines']['bullet_lines']

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_white_line_count(self, name):
        meta = load_sample_meta(name)
        img, _ = load_sample_image(name)
        w_mask = white_text_mask(img)
        lines = MabinogiTooltipSplitter().detect_centered_lines(w_mask)
        assert len(lines) == meta['lines']['white_lines']


@skip_no_images
class TestShapeWalkerConsistency:
    """Verify classify_cluster gives same result as detect_prefix_per_color.

    Both use shape walker internally, so results must always agree.
    Uses per-color detection on BGR crops (production path).
    """

    @pytest.mark.parametrize('name', [
        'captain_suit', 'dropbell', 'plate_helmet_simple',
        'dualgun', 'titan_blade',
    ])
    def test_direct_classify_matches_detect_prefix(self, name):
        """classify_cluster called directly on extracted cluster gives same
        result as detect_prefix_per_color."""
        img, _ = load_sample_image(name)
        h, w = img.shape[:2]

        for config in (BULLET_DETECTOR, SUBBULLET_DETECTOR):
            mask = config.build_mask(img)
            splitter = MabinogiTooltipSplitter()
            lines = splitter.detect_centered_lines(mask)

            for line in lines:
                x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
                pad_x = max(2, lh // 3)
                x0 = max(0, x - pad_x)
                x1 = min(w, x + lw + pad_x)
                bgr_crop = img[y:y + lh, x0:x1]

                info = detect_prefix_per_color(bgr_crop, config=config)
                if info['type'] is None:
                    continue

                # Extract cluster from the config mask crop
                mask_crop = mask[y:y + lh, x0:x1]
                cluster_region = mask_crop[:, info['x']:info['x'] + info['w']]
                match = classify_cluster(cluster_region, [SHAPE_NIEUN, SHAPE_DOT])

                assert match is not None, (
                    f'{name}: detect_prefix_per_color found {info["type"]} at y={y} but '
                    f'classify_cluster returned None on the cluster region'
                )

                expected_type = 'subbullet' if match.shape.name == 'ㄴ' else 'bullet'
                assert expected_type == info['type'], (
                    f'{name}: mismatch at y={y}: '
                    f'detect_prefix_per_color={info["type"]}, classify_cluster={match.shape.name}'
                )


@skip_no_images
class TestPerColorDetection:
    """Verify per-color prefix detection on BGR crops — the production path.

    Exercises detect_prefix_per_color() on BGR image crops, which is what
    the actual production code calls via the @detect_prefix decorator.
    """

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_per_color_count(self, name):
        meta = load_sample_meta(name)
        img, _ = load_sample_image(name)
        bullets = _count_prefixes_per_color(img, BULLET_DETECTOR)
        assert bullets == meta['prefix']['bullets']

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_subbullet_per_color_count(self, name):
        meta = load_sample_meta(name)
        img, _ = load_sample_image(name)
        subs = _count_prefixes_per_color(img, SUBBULLET_DETECTOR)
        assert subs == meta['prefix']['subbullets']
