from rapidfuzz import process, fuzz
import os
import re

# Number normalization patterns
_NUM_PAT    = re.compile(r'\d+(?:\.\d+)?')          # digit sequences (incl. decimals)
_TMPL_N     = re.compile(r'(?<!\w)n(?!\w)')          # standalone 'n' placeholder in dict entries
_PREFIX_PAT = re.compile(r'^[-ㄴ]\s*')               # leading structural prefixes (- or ㄴ) to strip before matching


def _normalize_nums(text):
    """Replace digit sequences and standalone template 'n' with N."""
    text = _NUM_PAT.sub('N', text)
    text = _TMPL_N.sub('N', text)
    return text


class TextCorrector:
    def __init__(self, dictionary_path=None):
        self.dictionary = []
        self._norm_cache = []   # list of (normalized_entry, original_entry)
        if dictionary_path and os.path.exists(dictionary_path):
            self.load_dictionary(dictionary_path)
        else:
            print(f"Warning: Dictionary not found at {dictionary_path}")

    def load_dictionary(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            new_entries = [line.strip() for line in f if line.strip()]
        self.dictionary.extend(new_entries)
        self._norm_cache = [(_normalize_nums(e), e) for e in self.dictionary]
        print(f"TextCorrector loaded {len(new_entries)} entries from {os.path.basename(path)} (total: {len(self.dictionary)})")

    def correct(self, text, cutoff_score=80):
        """
        Fuzzy match against dictionary (no number normalization).
        Returns: (corrected_text, score)
        If no match above cutoff_score, returns (original_text, 0)
        """
        if not text or not self.dictionary:
            return text, 0

        result = process.extractOne(text, self.dictionary, scorer=fuzz.ratio)
        if result:
            match, score, _ = result
            if score >= cutoff_score:
                return match, score

        return text, 0

    def correct_normalized(self, text, cutoff_score=80):
        """
        Fuzzy match with number normalization and prefix handling.

        Numbers in OCR text are replaced with N before matching, then re-injected
        from the OCR text into the matched template. Leading structural prefixes
        (ㄴ or -) are stripped before matching and re-attached to the result.

        This handles dictionary entries where numbers vary (e.g. 'n% 증가' or
        '10% 증가' for a range of values).

        Returns: (corrected_text, score)
        If no match above cutoff_score, returns (original_text, 0)
        """
        if not text or not self._norm_cache:
            return text, 0

        # Separate leading structural prefix from content
        prefix_m = _PREFIX_PAT.match(text)
        prefix = prefix_m.group(0) if prefix_m else ''
        core = text[len(prefix):]

        if not core:
            return text, 0

        # Extract numbers from core for reconstruction after matching
        numbers = _NUM_PAT.findall(core)
        norm_core = _normalize_nums(core)

        # Find best match among normalized dictionary entries
        best_score = 0
        best_norm = None
        for norm_entry, _ in self._norm_cache:
            score = fuzz.ratio(norm_core, norm_entry)
            if score > best_score:
                best_score = score
                best_norm = norm_entry

        if best_score >= cutoff_score and best_norm is not None:
            # Re-inject OCR numbers left-to-right into the matched template
            result = best_norm
            for num in numbers:
                result = result.replace('N', num, 1)
            return prefix + result, best_score

        return text, 0
