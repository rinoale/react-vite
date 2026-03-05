"""Tests for detect_centered_lines — synthetic and real-image tests."""

import numpy as np
import pytest

from lib.pipeline.line_split import TooltipLineSplitter, MabinogiTooltipSplitter
from lib.image_processors.prefix_detector import bullet_text_mask

from sample_image_helpers import IMAGE_NAMES, skip_no_images, load_sample_image, load_sample_meta


class TestDetectCenteredLines:
    def _make_splitter(self):
        return TooltipLineSplitter()

    def _make_binary_image(self, height, width, bands):
        """Create a binary image with horizontal text bands (ocr_binary convention).

        Args:
            height: image height
            width: image width
            bands: list of (y_start, y_end) for ink stripes (text)

        Returns:
            uint8 array with 255 background, 0 ink text bands.
        """
        img = np.full((height, width), 255, dtype=np.uint8)
        for y_start, y_end in bands:
            # Fill text band across most of the width (avoid edge border detection)
            img[y_start:y_end, 10:width - 10] = 0
        return img

    def test_three_line_bands(self):
        splitter = self._make_splitter()
        # 3 text bands of height ~12, separated by gaps of ~6
        bands = [(10, 22), (28, 40), (46, 58)]
        img = self._make_binary_image(80, 200, bands)
        lines = splitter.detect_centered_lines(img)
        assert len(lines) == 3
        # Lines should be sorted by y position
        ys = [l['y'] for l in lines]
        assert ys == sorted(ys)

    def test_empty_image(self):
        splitter = self._make_splitter()
        img = np.full((80, 200), 255, dtype=np.uint8)
        lines = splitter.detect_centered_lines(img)
        assert len(lines) == 0

    def test_single_line(self):
        splitter = self._make_splitter()
        bands = [(20, 34)]
        img = self._make_binary_image(60, 200, bands)
        lines = splitter.detect_centered_lines(img)
        assert len(lines) == 1
        # 14px ink band → centered 13px window
        assert lines[0]['height'] == 13

    def test_line_dimensions(self):
        splitter = self._make_splitter()
        bands = [(10, 22)]
        img = self._make_binary_image(40, 200, bands)
        lines = splitter.detect_centered_lines(img)
        assert len(lines) == 1
        line = lines[0]
        assert line['width'] >= 10  # min_width check
        assert line['height'] == 13  # centered window is always min_height


@skip_no_images
class TestDetectCenteredLinesOnImages:
    """Verify detect_centered_lines on real tooltip images against ground truth."""

    @pytest.mark.parametrize('name', IMAGE_NAMES)
    def test_bullet_line_count(self, name):
        meta = load_sample_meta(name)
        img, _ = load_sample_image(name)
        b_mask = bullet_text_mask(img)
        lines = MabinogiTooltipSplitter().detect_centered_lines(b_mask)
        assert len(lines) == meta['lines']['bullet_lines']
