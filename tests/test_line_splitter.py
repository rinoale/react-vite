"""Tests for backend/lib/tooltip_line_splitter.py — uses synthetic numpy images."""

import numpy as np
import tempfile

from lib.tooltip_line_splitter import TooltipLineSplitter


class TestDetectTextLines:
    def _make_splitter(self):
        return TooltipLineSplitter(output_dir=tempfile.mkdtemp())

    def _make_binary_image(self, height, width, bands):
        """Create a binary image with horizontal text bands.

        Args:
            height: image height
            width: image width
            bands: list of (y_start, y_end) for white stripes (text)

        Returns:
            uint8 array with 0 background, 255 text bands.
        """
        img = np.zeros((height, width), dtype=np.uint8)
        for y_start, y_end in bands:
            # Fill text band across most of the width (avoid edge border detection)
            img[y_start:y_end, 10:width - 10] = 255
        return img

    def test_three_line_bands(self):
        splitter = self._make_splitter()
        # 3 text bands of height ~12, separated by gaps of ~6
        bands = [(10, 22), (28, 40), (46, 58)]
        img = self._make_binary_image(80, 200, bands)
        lines = splitter.detect_text_lines(img)
        assert len(lines) == 3
        # Lines should be sorted by y position
        ys = [l['y'] for l in lines]
        assert ys == sorted(ys)

    def test_empty_image(self):
        splitter = self._make_splitter()
        img = np.zeros((80, 200), dtype=np.uint8)
        lines = splitter.detect_text_lines(img)
        assert len(lines) == 0

    def test_single_line(self):
        splitter = self._make_splitter()
        bands = [(20, 34)]
        img = self._make_binary_image(60, 200, bands)
        lines = splitter.detect_text_lines(img)
        assert len(lines) == 1
        assert lines[0]['height'] == 14

    def test_line_dimensions(self):
        splitter = self._make_splitter()
        bands = [(10, 22)]
        img = self._make_binary_image(40, 200, bands)
        lines = splitter.detect_text_lines(img)
        assert len(lines) == 1
        line = lines[0]
        assert line['width'] >= 10  # min_width check
        assert 6 <= line['height'] <= 25  # within default min/max
