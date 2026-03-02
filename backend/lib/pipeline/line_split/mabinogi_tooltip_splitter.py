"""Mabinogi-specific line splitter: UI border removal + artifact filtering."""

import numpy as np

from .line_splitter import TooltipLineSplitter


class MabinogiTooltipSplitter(TooltipLineSplitter):
    """Extends TooltipLineSplitter with Mabinogi tooltip UI border handling.

    Overrides:
        _remove_borders: Masks narrow vertical UI border columns (│) that
            bridge gaps between text lines.
        _filter_clusters: Removes border artifacts from ink clusters:
            thin vertical border lines, horizontal bar separators (ㅡㅡㅡ),
            and corner bracket decorations (「).
    """

    def _remove_borders(self, binary_img):
        """Remove narrow vertical border columns that interfere with line detection.

        Mabinogi tooltip images have thin UI border lines (1-2px wide columns
        that span many rows).  These contribute white pixels per row that
        prevent gap detection between text lines.

        Only removes narrow runs (<=3px wide) of high-density columns.
        Wider runs are aligned text content (e.g. repeated ㄴ, - prefixes).
        """
        h, w = binary_img.shape
        cleaned = binary_img.copy()

        # Columns with >60% vertical density are genuine UI borders.
        col_density = np.sum(binary_img > 0, axis=0) / h
        is_dense = col_density > 0.6

        # Only mask narrow runs (<=3px wide)
        in_run = False
        run_start = 0
        for col in range(w):
            if is_dense[col] and not in_run:
                run_start = col
                in_run = True
            elif not is_dense[col] and in_run:
                run_width = col - run_start
                if run_width <= 3:
                    cleaned[:, run_start:col] = 0
                in_run = False
        if in_run:
            run_width = w - run_start
            if run_width <= 3:
                cleaned[:, run_start:w] = 0

        return cleaned

    def _filter_clusters(self, clusters, col_projection, line_h):
        """Filter out Mabinogi tooltip UI border artifacts from ink clusters.

        Removes:
        1. Thin clusters (1-2px wide) far from text — vertical border lines (│)
        2. Wide clusters with low column density — horizontal bar borders (ㅡㅡㅡ)
        3. Corner bracket artifacts (「) before section headers
        """
        if len(clusters) <= 1:
            return clusters

        gap_threshold = line_h * 2

        # Identify text clusters: wider than 2px with sufficient ink density.
        text_clusters = []
        for cs, ce in clusters:
            cw = ce - cs + 1
            if cw <= 2:
                continue
            avg_density = float(np.mean(col_projection[cs:ce + 1]))
            # Wide + low density = horizontal bar border
            if cw > line_h * 3 and avg_density < 2.0:
                continue
            text_clusters.append((cs, ce))

        if not text_clusters:
            return clusters

        filtered = []
        for idx, (cs, ce) in enumerate(clusters):
            cw = ce - cs + 1
            avg_density = float(np.mean(col_projection[cs:ce + 1]))

            # Skip horizontal bar borders
            if cw > line_h * 3 and avg_density < 2.0:
                continue

            if cw > 2:
                # Corner bracket artifact (e.g. 「 before section headers):
                # First cluster only, with low ink density and clear gap to main text.
                # Real text characters have avg_density >= 3.5; the 「 bracket is ~1.8.
                if idx == 0 and avg_density < 2.0:
                    if idx + 1 < len(clusters):
                        gap_to_next = clusters[idx + 1][0] - ce - 1
                        if gap_to_next >= 4:
                            continue  # drop corner bracket
                filtered.append((cs, ce))
                continue

            # Thin cluster: check distance to nearest text cluster
            min_dist = min(
                min(abs(cs - tce), abs(ce - tcs))
                for tcs, tce in text_clusters
            )
            if min_dist <= gap_threshold:
                # Full-height border stripe (│): spans nearly all rows → remove.
                if avg_density >= line_h * 0.85:
                    continue
                filtered.append((cs, ce))

        return filtered if filtered else clusters
