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


def find_best_pairs(queries, candidates, scorer=None):
    """Greedy 1:1 best-match assignment between queries and candidates.

    Scores all (query, candidate) pairs, then assigns greedily from highest
    score down. Each query matches at most one candidate and vice versa.

    Args:
        queries:    list of items to match.
        candidates: list of items to match against.
        scorer:     fn(query, candidate) -> numeric score.  Default: fuzz.ratio.

    Returns:
        list parallel to queries: (candidate_index, score) per query.
        Unmatched queries get (-1, 0).
    """
    if scorer is None:
        scorer = fuzz.ratio

    n_q = len(queries)
    n_c = len(candidates)
    if n_q == 0 or n_c == 0:
        return [(-1, 0)] * n_q

    scored = []
    for qi in range(n_q):
        for ci in range(n_c):
            scored.append((scorer(queries[qi], candidates[ci]), qi, ci))
    scored.sort(reverse=True)

    used_q = set()
    used_c = set()
    result = [(-1, 0)] * n_q

    for score, qi, ci in scored:
        if qi in used_q or ci in used_c:
            continue
        if score <= 0:
            break
        result[qi] = (ci, score)
        used_q.add(qi)
        used_c.add(ci)

    return result


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
