"""Mabinogi-specific tooltip parser.

Structural parsing of tooltip OCR results: grouping, section tagging,
reforge/enchant/color structure extraction.
"""

import re
from pathlib import Path

import yaml

# Reforge section patterns
# Flexible: two digit groups near 레벨 at end, optional parens, any non-digit separator
# Matches: '보호(13/20 레벨)', '보호13/20 레벨)', '보호 13 20 레벨'
_REFORGE_LEVEL_RE = re.compile(r'^[-\s]*(.+?)\s*\(?(\d+)\D+(\d+)\s*레벨\)?\s*$')

# Enchant section patterns
# Header: '[접두] 충격을 (랭크 F)' or '[접미] 관리자 (랭크 6)' — ranks: A-F or 1-9
_ENCHANT_HEADER_RE = re.compile(r'^\[?(접두|접미)\]?\s+(.+?)\s*\(랭크\s*([A-F0-9]+)\)')

# Effect number extraction: 'stat_name NUMBER[%] direction'
# Group 1: stat name, Group 2: number, Group 3: optional %, Group 4: rest (증가/감소/etc.)
_EFFECT_NUM_RE = re.compile(r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(%?)\s*(.*)$')


def _parse_effect_number(text):
    """Extract option_name and option_level from an effect text.

    Examples:
        '최대대미지 53 증가'                       → ('최대대미지', 53)
        '아르카나 스킬 보너스 대미지 1% 증가'      → ('아르카나 스킬 보너스 대미지', 1)
        '활성화된 아르카나의 전용 옵션일 때 효과 발동' → (None, None)

    Returns:
        (option_name, option_level) or (None, None) if no number found.
    """
    m = _EFFECT_NUM_RE.match(text.strip())
    if not m:
        return None, None
    name = m.group(1).strip()
    num_str = m.group(2)
    level = float(num_str) if '.' in num_str else int(num_str)
    return name, level


class MabinogiTooltipParser:

    def __init__(self, config_path):
        self.config = yaml.safe_load(Path(config_path).read_text())
        self.sections_config = self.config.get('sections', {})


    def _parse_pre_header(self, ocr_results):
        """Return all pre-header lines as a single 'pre_header' section.

        No special-case splitting — every line before the first orange header
        is simply tagged 'pre_header' and passed through.
        """
        for line in ocr_results:
            line['section'] = 'pre_header'
        return {'pre_header': {
            'lines': ocr_results,
            'text': ' '.join(l['text'] for l in ocr_results),
        }}

    @staticmethod
    def _detect_sub_lines(lines):
        """Tag lines as sub-lines based on prefix detection.

        Lines with _prefix_type == 'subbullet' are tagged is_reforge_sub=True.
        """
        for line in lines:
            if line.get('is_header'):
                continue
            if 'reforge_name' in line:
                continue
            line['is_reforge_sub'] = line.get('_prefix_type') == 'subbullet'

    def _parse_reforge_section(self, lines):
        """Parse reforge section into structured option records.

        Each reforge option is a main line (at baseline x), optionally followed
        by an indented sub-bullet describing the effect. Some options have a
        '(current/max 레벨)' level suffix, others don't.

        Tags each line dict with metadata for FM and DB storage:
          main line with levels:    reforge_name, reforge_level, reforge_max_level, is_reforge_sub=False
          main line without levels: reforge_name (text as-is), is_reforge_sub=False
          sub-bullet:               is_reforge_sub=True

        Returns:
            {'options': [{name, level, max_level, option_name, option_level, effect}], 'lines': lines}
        """
        # First pass: detect level-suffixed options via regex
        for line in lines:
            text = line.get('text', '')
            m = _REFORGE_LEVEL_RE.match(text)
            if m:
                line['reforge_name']      = m.group(1).strip().lstrip('-').strip()
                line['reforge_level']     = int(m.group(2))
                line['reforge_max_level'] = int(m.group(3))
                line['is_reforge_sub']    = False

        # Second pass: detect sub-lines by prefix type
        self._detect_sub_lines(lines)

        # Third pass: non-indented lines without reforge_name are level-less options
        for line in lines:
            if line.get('is_header'):
                continue
            if 'reforge_name' in line:
                continue
            if line.get('is_reforge_sub'):
                continue
            text = line.get('text', '').strip().lstrip('-').strip()
            if text:
                line['reforge_name']      = text
                line['reforge_level']     = None
                line['reforge_max_level'] = None
                line['is_reforge_sub']    = False

        result = self.build_reforge_structured(lines)
        result['lines'] = lines
        return result

    def build_reforge_structured(self, lines):
        """Build reforge options array from tagged lines.

        Call after FM correction to get option_name from corrected text.
        Lines must already be tagged by _parse_reforge_section.

        Returns:
            {'options': [{name, level, max_level, option_name, option_level, effect, raw_text}]}
        """
        options = []
        current = None

        for line in lines:
            if line.get('is_header'):
                continue

            text = line.get('text', '')

            if not line.get('is_reforge_sub', True) and 'reforge_name' in line:
                m = _REFORGE_LEVEL_RE.match(text)
                if m:
                    name      = m.group(1).strip().lstrip('-').strip()
                    level     = int(m.group(2))
                    max_level = int(m.group(3))
                else:
                    name      = text.strip().lstrip('-').strip() or line['reforge_name']
                    level     = line.get('reforge_level')
                    max_level = line.get('reforge_max_level')

                current = {
                    'name':         name,
                    'level':        level,
                    'max_level':    max_level,
                    'option_name':  name,
                    'option_level': level,
                    'effect':       None,
                    'text':         line.get('raw_text', text),
                    'line_index': line.get('line_index'),
                }
                options.append(current)

            elif line.get('is_reforge_sub') and current is not None:
                current['effect'] = text.strip()

        return {'options': options}

    def _parse_enchant_section(self, lines):
        """Parse enchant section into prefix/suffix slot records.

        Each enchant is a header '[접두|접미] NAME (랭크 RANK)' followed by
        effect lines starting with '-'.

        Tags each line dict with metadata for FM and DB storage:
          header line: enchant_slot, enchant_name, enchant_rank, is_enchant_hdr=True
          effect line: is_enchant_hdr=False

        Returns:
            {'prefix': {text, name, rank, effects} | None,
             'suffix': {text, name, rank, effects} | None,
             'lines': lines}
        """
        for line in lines:
            text = line.get('text', '')
            m = _ENCHANT_HEADER_RE.match(text)
            if m:
                line['enchant_slot']   = m.group(1)
                line['enchant_name']   = m.group(2).strip()
                line['enchant_rank']   = m.group(3)
                line['is_enchant_hdr'] = True
            else:
                line['is_enchant_hdr'] = False

        result = self.build_enchant_structured(lines)
        result['lines'] = lines
        return result

    def build_enchant_structured(self, lines):
        """Build enchant prefix/suffix dicts from tagged lines.

        Call after FM correction to get names/effects from corrected text.
        Lines must already be tagged by _parse_enchant_section.

        Each effect is a dict with 'text' and optional 'option_name'/'option_level'
        extracted by _parse_effect_number().

        Returns:
            {'prefix': {text, name, rank, effects} | None,
             'suffix': {text, name, rank, effects} | None}
        """
        prefix = None
        suffix = None
        current = None

        for line in lines:
            if line.get('is_header'):
                continue

            if line.get('is_enchant_hdr'):
                text = line['text']
                m = _ENCHANT_HEADER_RE.match(text)
                if m:
                    name = m.group(2).strip()
                    rank = m.group(3)
                else:
                    name = line.get('enchant_name', '')
                    rank = line.get('enchant_rank', '')

                # Enrich text with rank from DB if available but not in OCR output
                display_text = text
                if name and rank and '랭크' not in text:
                    display_text = f"[{line.get('enchant_slot', '접두')}] {name} (랭크 {rank})"

                current = {'text': display_text, 'name': name, 'rank': rank, 'effects': []}
                slot = line.get('enchant_slot', '')
                if slot == '접두':
                    prefix = current
                elif slot == '접미':
                    suffix = current

            elif current is not None:
                eff_text = line['text'].strip().lstrip('-').strip()
                if eff_text:
                    entry = {'text': eff_text, 'line_index': line.get('line_index')}
                    opt_name, opt_level = _parse_effect_number(eff_text)
                    if opt_name is not None:
                        entry['option_name']  = opt_name
                        entry['option_level'] = opt_level
                    current['effects'].append(entry)

        return {'prefix': prefix, 'suffix': suffix}

    def _parse_color_section(self, lines):
        """Parse color part lines structurally.

        Color part lines are horizontally split into sub-segments:
        "파트 A", "R:0", "G:0", "B:12"

        Instead of relying on OCR for the full sparse line, we parse
        each sub-segment individually.

        Returns:
            dict with 'parts' list of {part, r, g, b} dicts
        """
        parts = []
        for line in lines:
            sub_lines = line.get('sub_lines', [])
            if not sub_lines:
                # Single line, try to parse from full text
                part_data = self._parse_color_text(line.get('text', ''))
                if part_data:
                    parts.append(part_data)
                continue

            # Parse from sub-line texts
            part_name = None
            r, g, b = None, None, None
            for sub in sub_lines:
                text = sub.get('text', '').strip()
                if not text:
                    continue

                # Check for part name (파트 A, 파트 B, etc.)
                part_match = re.search(r'파트\s*([A-F])', text)
                if part_match:
                    part_name = part_match.group(1)
                    continue

                # Check for R:N, G:N, B:N
                rgb_match = re.search(r'([RGB])\s*[:\s]\s*(\d+)', text)
                if rgb_match:
                    channel = rgb_match.group(1)
                    value = int(rgb_match.group(2))
                    if channel == 'R':
                        r = value
                    elif channel == 'G':
                        g = value
                    elif channel == 'B':
                        b = value

            if part_name is not None:
                parts.append({
                    'part': part_name,
                    'r': r,
                    'g': g,
                    'b': b,
                })

        return {'parts': parts}

    def _parse_color_text(self, text):
        """Parse a color part from a single text string.

        Handles: "파트 A R:0 G:0 B:12", "- 파트 A R:0 G:0 B:0"
        """
        part_match = re.search(r'파트\s*([A-F])', text)
        if not part_match:
            return None

        part_name = part_match.group(1)
        r_match = re.search(r'R\s*[:\s]\s*(\d+)', text)
        g_match = re.search(r'G\s*[:\s]\s*(\d+)', text)
        b_match = re.search(r'B\s*[:\s]\s*(\d+)', text)

        return {
            'part': part_name,
            'r': int(r_match.group(1)) if r_match else None,
            'g': int(g_match.group(1)) if g_match else None,
            'b': int(b_match.group(1)) if b_match else None,
        }
