"""LEGACY — no longer used by the V3 pipeline.

DualReader wraps two EasyOCR readers, picks higher confidence per line.
Superseded by PreHeaderHandler._pick_best_per_line (dual-preprocessing merge)
and font_reader selection (pre_header detects font, content sections use a
single font-matched reader).
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
        """Run all readers on the same image, pick highest confidence per line position.

        Returns list of (bbox, text, confidence) tuples.
        After each call, self.last_model_names contains the winning model name
        per line position (same length as the returned list).
        """
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
            self.last_model_names = []
            return []

        # If only one reader returned results, use it directly
        if len(all_results) == 1:
            self.last_model_names = [self.names[0]] * len(all_results[0])
            return all_results[0]

        # Merge: for each line position, pick the result with higher confidence
        # Results are lists of (bbox, text, confidence) tuples
        merged = []
        model_names = []
        for items in zip(*all_results):
            best_idx = max(range(len(items)), key=lambda i: items[i][2])
            merged.append(items[best_idx])
            model_names.append(self.names[best_idx])

        # Handle case where readers return different numbers of results
        # (shouldn't happen with same input, but be defensive)
        max_len = max(len(r) for r in all_results)
        if len(merged) < max_len:
            longest_idx = max(range(len(all_results)), key=lambda i: len(all_results[i]))
            longest = all_results[longest_idx]
            merged.extend(longest[len(merged):])
            model_names.extend([self.names[longest_idx]] * (max_len - len(model_names)))

        self.last_model_names = model_names
        return merged
