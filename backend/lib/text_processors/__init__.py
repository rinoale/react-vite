"""Text correction: generic fuzzy matching and Mabinogi-specific FM."""

from .common import TextCorrector, _normalize_nums, _NUM_PAT, find_best_pairs
from .mabinogi import MabinogiTextCorrector, _PREFIX_PAT
