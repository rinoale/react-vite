"""DualReader: wraps two EasyOCR readers, picks higher confidence per line.

Zero changes needed to mabinogi_tooltip_parser.py — the parser sees one
"reader" object. Line splitting runs once; each recognize() call runs both
models and merges results by confidence.
"""


class DualReader:
    """Wraps two EasyOCR readers; runs both on each image, picks higher confidence."""

    def __init__(self, readers, names):
        """
        Args:
            readers: list of patched EasyOCR Reader instances
            names: list of reader names (for logging/debugging)
        """
        self.readers = readers
        self.names = names

    def recognize(self, img_cv_grey, horizontal_list=None, free_list=None, **kwargs):
        """Run all readers on the same image, pick highest confidence per line position."""
        all_results = []
        for reader in self.readers:
            result = reader.recognize(
                img_cv_grey,
                horizontal_list=horizontal_list,
                free_list=free_list,
                **kwargs,
            )
            all_results.append(result)

        if not all_results:
            return []

        # If only one reader returned results, use it directly
        if len(all_results) == 1:
            return all_results[0]

        # Merge: for each line position, pick the result with higher confidence
        # Results are lists of (bbox, text, confidence) tuples
        merged = []
        for items in zip(*all_results):
            best = max(items, key=lambda x: x[2])  # x[2] = confidence
            merged.append(best)

        # Handle case where readers return different numbers of results
        # (shouldn't happen with same input, but be defensive)
        max_len = max(len(r) for r in all_results)
        if len(merged) < max_len:
            # Append remaining items from the longest result
            longest = max(all_results, key=len)
            merged.extend(longest[len(merged):])

        return merged
