from rapidfuzz import process, fuzz
import os
import re

# Number normalization patterns
_NUM_PAT    = re.compile(r'\d+(?:\.\d+)?')   # digit sequences (incl. decimals)
_TMPL_N     = re.compile(r'(?<!\w)n(?!\w)')  # standalone 'n' placeholder in dict entries
_PREFIX_PAT = re.compile(r'^[-ㄴ]\s*')       # leading structural prefixes (- or ㄴ) to strip before matching

# Section-specific preprocessing patterns
# reforge: strip '(15/20 레벨)' level suffix before FM matching
_REFORGE_LEVEL_PAT = re.compile(r'\s*\(\d+/\d+\s*레벨\)\s*$')
# reforge: ㄴ sub-bullets describe effects at current level — never in dictionary
_REFORGE_SUB_RE    = re.compile(r'^\s*ㄴ')
# enchant: header line '[접두] 충격을 (랭크 F)' or '[접미] 관리자 (랭크 6)' — ranks: A-F or 1-9
_ENCHANT_HDR_PAT   = re.compile(r'^\[?(접두|접미)\]?\s+(.+?)\s*\(랭크\s*[A-F0-9]+\)')
# enchant: dictionary file header '[접미] 관리자 (랭크 6)' — strict form for parsing
_ENCHANT_FILE_HDR  = re.compile(r'^\[(접두|접미)\]\s+(.+?)\s*\(랭크\s*([A-F0-9]+)\)\s*$')


def _normalize_nums(text):
    """Replace digit sequences and standalone template 'n' with N."""
    text = _NUM_PAT.sub('N', text)
    text = _TMPL_N.sub('N', text)
    return text


class TextCorrector:
    def __init__(self, dict_dir=None, dictionary_path=None):
        self.dictionary = []           # combined entries from all loaded files
        self._norm_cache = []          # combined normalized cache
        self._section_dicts = {}       # section_name → [entries]
        self._section_norm_cache = {}  # section_name → [(normalized, original)]
        # Structured enchant DB for two-phase matching
        self._enchant_db = []                    # list of enchant entry dicts
        self._enchant_headers_norm = []          # [(norm_header, entry)] for phase-1 FM

        if dict_dir and os.path.exists(dict_dir):
            self.load_dict_dir(dict_dir)
        elif dictionary_path:
            self.load_dictionary(dictionary_path)
        else:
            print("Warning: No dictionary source provided to TextCorrector")

    def load_dict_dir(self, dict_dir):
        """Load all .txt files in dict_dir, keyed by filename stem.

        Each file becomes a named section dictionary. For example,
        'reforge.txt' is loaded as section 'reforge', and fuzzy matching
        for a line in the reforge section will search only those entries.

        'enchant.txt' is additionally loaded as a structured DB via
        _load_enchant_structured() to support two-phase header+effect matching.
        """
        for fname in sorted(os.listdir(dict_dir)):
            if not fname.endswith('.txt'):
                continue
            section = fname[:-4]   # strip .txt → section name
            path = os.path.join(dict_dir, fname)

            if fname == 'enchant.txt':
                self._load_enchant_structured(path)
                # Also build flat entries for the combined dictionary
                entries = [line.strip() for line in open(path, encoding='utf-8') if line.strip()]
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    entries = [line.strip() for line in f if line.strip()]

            self._section_dicts[section] = entries
            self._section_norm_cache[section] = [(_normalize_nums(e), e) for e in entries]
            self.dictionary.extend(entries)
            print(f"TextCorrector loaded {len(entries):4d} entries  [{section}]  ({fname})")

        self._norm_cache = [(_normalize_nums(e), e) for e in self.dictionary]
        print(f"TextCorrector total: {len(self.dictionary)} entries across "
              f"{len(self._section_dicts)} section(s): {list(self._section_dicts)}")

    def load_dictionary(self, path):
        """Load a single dictionary file into the combined pool (no section key)."""
        with open(path, 'r', encoding='utf-8') as f:
            new_entries = [line.strip() for line in f if line.strip()]
        self.dictionary.extend(new_entries)
        self._norm_cache = [(_normalize_nums(e), e) for e in self.dictionary]
        print(f"TextCorrector loaded {len(new_entries)} entries from {os.path.basename(path)} "
              f"(total: {len(self.dictionary)})")

    def _load_enchant_structured(self, path):
        """Parse transformed enchant.txt into a structured two-phase match DB.

        Expected format (after enchant.txt transformation):
            [접미] 관리자 (랭크 6)
            무리아스의 유물에 인챈트 가능
            활성화된 아르카나의 전용 옵션일 때 효과 발동
            아르카나 스킬 보너스 대미지 1% 증가
            ...
            [접두] 소복한 (랭크 8)
            ...

        Builds:
            self._enchant_db           — list of entry dicts
            self._enchant_headers_norm — [(norm_header, entry)] for phase-1 header FM
        """
        with open(path, 'r', encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f]

        db = []
        current = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            m = _ENCHANT_FILE_HDR.match(stripped)
            if m:
                current = {
                    'header':       stripped,
                    'header_norm':  _normalize_nums(stripped),
                    'slot':         m.group(1),
                    'name':         m.group(2).strip(),
                    'rank':         m.group(3),
                    'effects':      [],
                    'effects_norm': [],
                }
                db.append(current)
            elif current is not None:
                current['effects'].append(stripped)
                current['effects_norm'].append((_normalize_nums(stripped), stripped))

        self._enchant_db = db
        self._enchant_headers_norm = [(e['header_norm'], e) for e in db]
        print(f"TextCorrector enchant structured DB: {len(db)} entries loaded from {os.path.basename(path)}")

    def match_enchant_header(self, text, cutoff_score=80):
        """Two-phase enchant matching — phase 1: match OCR header against enchant DB.

        The OCR line should look like '[접두] 충격을 (랭크 F)' or '[접미] 관리자 (랭크 6)'.
        FM is run against all canonical headers in _enchant_headers_norm.

        Returns:
            (corrected_header, score, entry) on match
            (original_text, 0, None)         on miss
        """
        if not text or not self._enchant_headers_norm:
            return text, 0, None

        norm_text = _normalize_nums(text)
        best_score = 0
        best_entry = None
        for norm_hdr, entry in self._enchant_headers_norm:
            score = fuzz.ratio(norm_text, norm_hdr)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= cutoff_score and best_entry is not None:
            return best_entry['header'], best_score, best_entry

        return text, 0, None

    def match_enchant_effect(self, text, entry, cutoff_score=75):
        """Two-phase enchant matching — phase 2: match OCR effect line against one enchant's effects.

        Searches only the ~4-8 effects of the given enchant entry, not the full dictionary.
        Numbers are normalized before matching and re-injected from OCR after matching.

        Args:
            text:  OCR text of the effect line (may start with '- ')
            entry: enchant DB entry dict from match_enchant_header phase 1

        Returns:
            (corrected_text, score) on match
            (original_text, 0)     on miss or no entry
        """
        if not text or not entry:
            return text, 0

        effects_norm = entry.get('effects_norm', [])
        if not effects_norm:
            return text, 0

        # Strip leading '-' prefix before matching, re-attach after
        prefix_m = _PREFIX_PAT.match(text)
        prefix = prefix_m.group(0) if prefix_m else ''
        core = text[len(prefix):]

        if not core:
            return text, 0

        numbers = _NUM_PAT.findall(core)
        norm_core = _normalize_nums(core)

        best_score = 0
        best_norm = None
        for norm_entry, _ in effects_norm:
            score = fuzz.ratio(norm_core, norm_entry)
            if score > best_score:
                best_score = score
                best_norm = norm_entry

        if best_score >= cutoff_score and best_norm is not None:
            result = best_norm
            for num in numbers:
                result = result.replace('N', num, 1)
            return prefix + result, best_score

        return text, 0

    def identify_enchant_from_effects(self, effect_texts, slot_type=None):
        """Identify an enchant entry by scoring OCR'd effect lines against all DB entries.

        Used when slot headers are detected by white-mask (no OCR text available).
        Matches effect lines against each enchant's known effects to find the best fit.

        Args:
            effect_texts: list of OCR'd effect strings (may include leading '- ')
            slot_type: '접두' or '접미' to narrow search (optional, falls back to all)

        Returns:
            (entry, rank_score) on match — rank_score is per-effect avg, higher = better
            (None, 0) on miss
        """
        if not effect_texts or not self._enchant_db:
            return None, 0

        def _score(candidates):
            # Pre-normalize OCR texts once
            norm_texts = []
            for text in effect_texts:
                core = _PREFIX_PAT.sub('', text).strip()
                if core:
                    norm_texts.append(_normalize_nums(core))

            best_entry = None
            best_rank = 0
            for entry in candidates:
                n_eff = len(entry['effects_norm'])
                if n_eff == 0:
                    continue
                # 1:1 matching: each entry effect matched at most once
                used = set()
                total = 0
                for norm in norm_texts:
                    best_score, best_idx = 0, -1
                    for idx, (norm_eff, _) in enumerate(entry['effects_norm']):
                        if idx in used:
                            continue
                        score = fuzz.ratio(norm, norm_eff)
                        if score > best_score:
                            best_score = score
                            best_idx = idx
                    if best_score > 60 and best_idx >= 0:
                        total += best_score
                        used.add(best_idx)
                # Normalize by entry effect count — bounded by 100
                rank = total / n_eff
                if rank > best_rank:
                    best_rank = rank
                    best_entry = entry
            # Threshold: avg per-effect score >= 50
            return (best_entry, best_rank) if best_rank >= 50 else (None, 0)

        # Try with slot_type filter first, fall back to all entries
        if slot_type:
            filtered = [e for e in self._enchant_db if e['slot'] == slot_type]
            entry, rank = _score(filtered)
            if entry:
                return entry, rank

        return _score(self._enchant_db)

    def correct(self, text, cutoff_score=80):
        """
        Fuzzy match against the combined dictionary (no number normalization).
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

    def correct_normalized(self, text, section=None, cutoff_score=80):
        """
        Fuzzy match with number normalization and prefix handling.

        If section is given and a matching dictionary file exists (e.g. section='reforge'
        looks up 'reforge.txt' entries), only that section's entries are searched.

        If section is given but no dictionary file exists for it, FM is skipped entirely
        and returns (original_text, -2) — callers should treat -2 as "no dictionary".

        If section is None (undetected), falls back to the combined dictionary.

        Numbers in OCR text are replaced with N before matching, then re-injected
        from the OCR text into the matched template. Leading structural prefixes
        (ㄴ or -) are stripped before matching and re-attached to the result.

        Returns: (corrected_text, score)
          score > 0  : matched entry from dictionary
          score == 0 : no match above cutoff
          score == -2: section known but no dictionary prepared — skipped
        """
        # Choose cache: section-specific if available;
        # skip entirely if section is known but has no dictionary;
        # fall back to combined only when section is unknown (None).
        if section and section in self._section_norm_cache:
            norm_cache = self._section_norm_cache[section]
        elif section:
            return text, -2   # known section, no dictionary prepared
        else:
            norm_cache = self._norm_cache

        if not text or not norm_cache:
            return text, 0

        # --- Section-specific early exit ---
        if section == 'reforge' and _REFORGE_SUB_RE.match(text):
            return text, -3   # ㄴ sub-bullet: effect description, never in reforge dictionary

        # Separate leading structural prefix from content
        prefix_m = _PREFIX_PAT.match(text)
        prefix = prefix_m.group(0) if prefix_m else ''
        core = text[len(prefix):]

        if not core:
            return text, 0

        # --- Section-specific core transformation ---
        reforge_level_suffix = ''   # level suffix to re-attach after matching
        if section == 'reforge':
            # Strip level suffix before matching: '스매시 대미지(15/20 레벨)' → '스매시 대미지'
            # Save suffix so it can be re-attached to the matched name
            m_lvl = _REFORGE_LEVEL_PAT.search(core)
            if m_lvl:
                reforge_level_suffix = m_lvl.group(0)
                core = _REFORGE_LEVEL_PAT.sub('', core).strip()
        elif section == 'enchant':
            # For header lines '[접두] 충격을 (랭크 F)', match only the enchant name.
            # Effect lines (starting with -) fall through and use full core as-is.
            m = _ENCHANT_HDR_PAT.match(text)
            if m:
                core   = m.group(2).strip()
                prefix = ''   # re-attach nothing — the result is the raw name

        if not core:
            return text, 0

        # Extract numbers from core for reconstruction after matching
        numbers = _NUM_PAT.findall(core)
        norm_core = _normalize_nums(core)

        # Find best match in the selected cache
        best_score = 0
        best_norm = None
        for norm_entry, _ in norm_cache:
            score = fuzz.ratio(norm_core, norm_entry)
            if score > best_score:
                best_score = score
                best_norm = norm_entry

        if best_score >= cutoff_score and best_norm is not None:
            # Re-inject OCR numbers left-to-right into the matched template
            result = best_norm
            for num in numbers:
                result = result.replace('N', num, 1)
            # Re-attach reforge level suffix that was stripped before matching
            return prefix + result + reforge_level_suffix, best_score

        return text, 0
