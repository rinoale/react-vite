import os
from pathlib import Path
from rapidfuzz import process, fuzz
import re

import yaml

# Load canonical prefix characters from tooltip config (game constants, not model-specific).
_tooltip_cfg = yaml.safe_load((Path(__file__).parents[2] / 'configs' / 'mabinogi_tooltip.yaml').read_text())
_BULLET = _tooltip_cfg['prefixes']['bullet']
_SUBBULLET = _tooltip_cfg['prefixes']['subbullet']

# Number normalization patterns
_NUM_PAT    = re.compile(r'\d+(?:\.\d+)?')   # digit sequences (incl. decimals)
_TMPL_N     = re.compile(r'(?<!\w)n(?!\w)')  # standalone 'n' placeholder in dict entries
_PREFIX_PAT = re.compile(rf'^[{re.escape(_BULLET)}\-,{re.escape(_SUBBULLET)}L]\s*')  # canonical prefixes from config + OCR misreadings (. → - or ,   ㄴ → L)

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
        """Load dictionary files in dict_dir, keyed by section name.

        Each .txt file becomes a named section dictionary. For example,
        'reforge.txt' is loaded as section 'reforge', and fuzzy matching
        for a line in the reforge section will search only those entries.

        Special handling:
        - enchant.yaml (in data/source_of_truth/) → structured DB via _load_enchant_structured()
        - 'enchant_*.txt' (enchant_slot_header.txt, enchant_effect.txt) → merged into section 'enchant'
        """
        # First pass: load enchant.yaml for structured DB
        sot_dir = os.path.join(os.path.dirname(dict_dir), 'source_of_truth')
        yaml_path = os.path.join(sot_dir, 'enchant.yaml')
        if os.path.exists(yaml_path):
            self._load_enchant_structured(yaml_path)

        for fname in sorted(os.listdir(dict_dir)):
            if not fname.endswith('.txt'):
                continue
            path = os.path.join(dict_dir, fname)

            # enchant_*.txt files merge into section 'enchant'
            if fname.startswith('enchant_'):
                section = 'enchant'
            else:
                section = fname[:-4]   # strip .txt → section name

            with open(path, 'r', encoding='utf-8') as f:
                entries = [line.strip() for line in f if line.strip()]

            if section in self._section_dicts:
                self._section_dicts[section].extend(entries)
            else:
                self._section_dicts[section] = entries
            self.dictionary.extend(entries)
            print(f"TextCorrector loaded {len(entries):4d} entries  [{section}]  ({fname})")

        # Build norm caches after all files loaded (enchant section may have been merged)
        for section, entries in self._section_dicts.items():
            self._section_norm_cache[section] = [(_normalize_nums(e), e) for e in entries]

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
        """Load enchant.yaml into a structured two-phase match DB.

        Reads YAML list of entries with slot/name/rank/effects fields.
        Reconstructs header and normalized forms for FM matching.

        Builds:
            self._enchant_db           — list of entry dicts
            self._enchant_headers_norm — [(norm_header, entry)] for phase-1 header FM
        """
        data = yaml.safe_load(Path(path).read_text())

        db = []
        for item in data:
            header = f"[{item['slot']}] {item['name']} (랭크 {item['rank']})"
            effects = item.get('effects', [])
            entry = {
                'header':       header,
                'header_norm':  _normalize_nums(header),
                'slot':         item['slot'],
                'name':         item['name'],
                'rank':         str(item['rank']),
                'effects':      effects,
                'effects_norm': [(_normalize_nums(e), e) for e in effects],
            }
            db.append(entry)

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

    def _dullahan_score_body(self, norm_effects, entry):
        """Score OCR effect lines (the 'body') against one enchant entry's effects.

        Part of the dullahan algorithm: the body (effects) helps find the right
        head (header). Uses 1:1 matching (each entry effect matched at most once).
        Returns total of matched scores (NOT divided by n_eff) — this avoids
        penalizing entries with unmatched availability effects like '발에 인챈트 가능'.
        """
        effects_norm = entry.get('effects_norm', [])
        if not effects_norm or not norm_effects:
            return 0
        used = set()
        total = 0
        for norm in norm_effects:
            best_s, best_idx = 0, -1
            for idx, (norm_eff, _) in enumerate(effects_norm):
                if idx in used:
                    continue
                s = fuzz.ratio(norm, norm_eff)
                if s > best_s:
                    best_s = s
                    best_idx = idx
            if best_s > 50 and best_idx >= 0:
                total += best_s
                used.add(best_idx)
        return total

    def do_dullahan(self, header_text, effect_texts,
                     slot_type=None):
        """Find the correct head (header) for a body (effects).

        Like the Dullahan searching for its head — when the header OCR is
        garbled, the effect lines (body) identify the true enchant.

        Strategy:
        1. Pick up heads that look right (score by header name similarity)
        2. Try each head on the body (score effects against candidates)
        3. If no head fits, let the body find its own (effect-only search)
           the header OCR is likely wrong — search by effects alone
        4. Format: add rank only when the name was actually corrected

        This handles two cases:
        - Near-ties (폭단: 폭주=50%, 성단=50%) → effects break the tie
        - Confident but wrong (바드=100% but effects=0) → effect search finds 마녀

        Args:
            header_text:    OCR'd header line (e.g. '[접미] 바드')
            effect_texts:   list of OCR'd effect strings (non-grey, non-empty)
            slot_type:      '접두' or '접미' to narrow candidates (optional)

        Returns:
            (corrected_header, score, entry) on match
            (original_text, 0, None) on miss
        """
        if not header_text or not self._enchant_db:
            return header_text, 0, None

        # Extract just the enchant name from OCR text for matching.
        # OCR may produce '[접미] 바드 (랭크 9)' or '[접미] 바드' (no rank).
        m = _ENCHANT_HDR_PAT.match(header_text)
        if m:
            ocr_name = m.group(2).strip()
        else:
            m2 = re.match(r'\[?(접두|접미)\]?\s+(.+)', header_text)
            if m2:
                ocr_name = m2.group(2).strip()
            else:
                ocr_name = header_text.strip()

        norm_name = _normalize_nums(ocr_name)

        # Format: add rank only when the name was actually corrected
        def _fmt(entry):
            if entry['name'] == ocr_name:
                return f"[{entry['slot']}] {entry['name']}"
            return entry['header']  # full form with rank

        # Score all entries by name similarity
        candidates = []
        for entry in self._enchant_db:
            if slot_type and entry['slot'] != slot_type:
                continue
            score = fuzz.ratio(norm_name, _normalize_nums(entry['name']))
            candidates.append((score, entry))

        if not candidates:
            return header_text, 0, None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_name_score = candidates[0][0]

        # No effects available — header-only matching (same as old code)
        if not effect_texts:
            if best_name_score >= 80:
                entry = candidates[0][1]
                return _fmt(entry), best_name_score, entry
            return header_text, 0, None

        # Pre-normalize OCR effect texts
        norm_effects = []
        for text in effect_texts:
            core = _PREFIX_PAT.sub('', text).strip()
            if core:
                norm_effects.append(_normalize_nums(core))

        if not norm_effects:
            if best_name_score >= 80:
                entry = candidates[0][1]
                return _fmt(entry), best_name_score, entry
            return header_text, 0, None

        # Take header candidates within 15 points of best, min score 30
        cutoff = max(best_name_score - 15, 30)
        top = [(s, e) for s, e in candidates if s >= cutoff]

        # Score effects for each header candidate
        scored = []
        for name_score, entry in top:
            eff_total = self._dullahan_score_body(norm_effects, entry)
            scored.append((name_score, eff_total, entry))

        # Among candidates, pick the one with highest effect total
        scored.sort(key=lambda x: x[1], reverse=True)
        best_name, best_eff, best_entry = scored[0]

        if best_eff > 0:
            # Effects confirm (or break tie for) this candidate
            if best_name >= 80 or best_eff >= 120:
                return _fmt(best_entry), best_name, best_entry
            # Header score too low and effects not strong enough
            return header_text, 0, None

        # All header candidates have 0 effect match → header likely wrong
        # (e.g. 바드=100% but effects are magic mastery → actually 마녀)
        # Search all entries by effects alone
        best_alt_total = 0
        best_alt_entry = None
        search = [e for e in self._enchant_db
                  if not slot_type or e['slot'] == slot_type]
        for entry in search:
            total = self._dullahan_score_body(norm_effects, entry)
            if total > best_alt_total:
                best_alt_total = total
                best_alt_entry = entry

        if best_alt_entry and best_alt_total >= 100:
            return _fmt(best_alt_entry), best_alt_total, best_alt_entry

        # Fallback: return best header match
        if best_name_score >= 80:
            entry = candidates[0][1]
            return _fmt(entry), best_name_score, entry

        return header_text, 0, None

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

    def apply_fm(self, all_lines, sections):
        """Apply section-aware FM correction to OCR output lines.

        Strips structural prefixes (- or ㄴ), then runs FM per section.
        Mutates line['text'] in place and sets line['fm_applied'].
        Shared by /upload-item-v3 endpoint and test scripts.
        """
        # Strip structural prefixes (- or ㄴ) from content lines.
        # Dictionary entries don't have these prefixes.
        for line in all_lines:
            if line.get('is_header'):
                continue
            text = line.get('text', '')
            m = _PREFIX_PAT.match(text)
            if m:
                line['text'] = text[m.end():]

        enchant_db_ready = bool(self._enchant_db)
        fm_sections = set(self._section_norm_cache.keys())

        # Per-line FM for non-enchant sections
        for line in all_lines:
            raw_text = line.get('text', '')
            section = line.get('section', '')

            if not raw_text.strip():
                line['fm_applied'] = False
                continue

            if line.get('is_header'):
                line['fm_applied'] = False
                continue

            # Enchant handled separately below
            if section == 'enchant':
                line['fm_applied'] = False
                continue

            # Skip FM for reforge sub-lines (indented effect descriptions)
            if line.get('is_reforge_sub'):
                line['fm_applied'] = False
                continue

            if section in fm_sections:
                fm_text, fm_score = self.correct_normalized(raw_text, section=section)
            else:
                fm_text, fm_score = raw_text, 0

            if fm_score > 0:
                line['text'] = fm_text
                line['fm_applied'] = True
            else:
                line['fm_applied'] = False

        # Enchant FM
        if 'enchant' in sections and sections['enchant'].get('lines') and enchant_db_ready:
            enchant_lines = [l for l in sections['enchant']['lines']
                             if not l.get('is_header')]
            has_slot_hdrs = any(l.get('is_enchant_hdr') for l in enchant_lines)

            if has_slot_hdrs:
                # Group lines by slot header (white-mask detected)
                slots = []
                current_hdr, current_effects = None, []
                for line in enchant_lines:
                    if line.get('is_enchant_hdr'):
                        if current_hdr is not None:
                            slots.append((current_hdr, current_effects))
                        current_hdr = line
                        current_effects = []
                    elif current_hdr is not None:
                        current_effects.append(line)
                if current_hdr is not None:
                    slots.append((current_hdr, current_effects))

                for hdr_line, effect_lines in slots:
                    raw_hdr = hdr_line.get('text', '')
                    effect_texts = [l.get('text', '') for l in effect_lines
                                    if l.get('text', '').strip()
                                    and not l.get('is_grey')]
                    slot_type = hdr_line.get('enchant_slot', '')

                    fm_hdr, fm_score, entry = self.do_dullahan(
                        raw_hdr, effect_texts, slot_type=slot_type)

                    if fm_score > 0:
                        hdr_line['text'] = fm_hdr
                        hdr_line['fm_applied'] = True
                        if entry:
                            hdr_line['enchant_slot'] = entry['slot']
                            hdr_line['enchant_name'] = entry['name']
                            hdr_line['enchant_rank'] = entry['rank']
            else:
                # Fallback: old linear approach (regex-detected or no headers)
                current_entry = None
                for line in enchant_lines:
                    raw_text = line.get('text', '')
                    if not raw_text.strip():
                        continue
                    hdr_text, hdr_score, hdr_entry = self.match_enchant_header(raw_text)
                    if hdr_score > 0:
                        line['text'] = hdr_text
                        line['fm_applied'] = True
                        current_entry = hdr_entry
                    else:
                        fm_text, fm_score = self.match_enchant_effect(
                            raw_text, current_entry)
                        if fm_score > 0:
                            line['text'] = fm_text
                            line['fm_applied'] = True
