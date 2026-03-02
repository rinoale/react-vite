"""Generic text correction: fuzzy matching with number normalization."""

import os
import re

from rapidfuzz import process, fuzz


# Number normalization patterns
_NUM_PAT    = re.compile(r'\d+(?:\.\d+)?')   # digit sequences (incl. decimals)
_TMPL_N     = re.compile(r'(?<!\w)n(?!\w)')  # standalone 'n' placeholder in dict entries


def _normalize_nums(text):
    """Replace digit sequences and standalone template 'n' with N."""
    text = _NUM_PAT.sub('N', text)
    text = _TMPL_N.sub('N', text)
    return text


class TextCorrector:
    def __init__(self, dictionary_path=None):
        self.dictionary = []           # combined entries from all loaded files
        self._norm_cache = []          # combined normalized cache
        self._section_dicts = {}       # section_name -> [entries]
        self._section_norm_cache = {}  # section_name -> [(normalized, original)]

        if dictionary_path:
            self.load_dictionary(dictionary_path)

    def load_dictionary(self, path):
        """Load a single dictionary file into the combined pool (no section key)."""
        with open(path, 'r', encoding='utf-8') as f:
            new_entries = [line.strip() for line in f if line.strip()]
        self.dictionary.extend(new_entries)
        self._norm_cache = [(_normalize_nums(e), e) for e in self.dictionary]
        print(f"TextCorrector loaded {len(new_entries)} entries from {os.path.basename(path)} "
              f"(total: {len(self.dictionary)})")

    def correct(self, text, cutoff_score=80):
        """Fuzzy match against the combined dictionary (no number normalization).

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
