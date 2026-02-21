# Plan: Section-Aware Tooltip Parser

## Goal

Create a Mabinogi-specific tooltip parser that categorizes split lines into sections (item_name, item_attrs, enchant, reforge, etc.), enabling:
- Structured data extraction for DB storage (search/recommendation)
- Skipping unnecessary sections (flavor text, price)
- Structural parsing for known patterns (color parts) instead of OCR
- Horizontal splitting for sparse lines (color parts, price)
- Better OCR targeting by focusing on sections that matter

## Architecture

```
TooltipLineSplitter (base, unchanged)
  └─ MabinogiTooltipParser (child class)
       - Uses base splitter for line detection
       - Adds section detection + line categorization
       - Reads rules from configs/mabinogi_tooltip.yaml
```

### File Changes

1. **NEW: `backend/lib/mabinogi_tooltip_parser.py`** — `MabinogiTooltipParser` class
2. **NEW: `configs/mabinogi_tooltip.yaml`** — Section definitions, header patterns
3. **EDIT: `backend/main.py`** — Use `MabinogiTooltipParser` instead of `TooltipLineSplitter` in the v2 pipeline, return structured section data
4. **EDIT: `scripts/test_v2_pipeline.py`** — Update to handle section-aware output, recombine horizontally-split lines
5. **NO CHANGE: `backend/lib/tooltip_line_splitter.py`** — Base class stays generic

## Section Definitions

From analyzing all 5 GT tooltips, here are the sections in order of appearance:

| Section Key | Header Pattern | Required? | OCR Strategy |
|-------------|---------------|-----------|--------------|
| `item_name` | First line(s) before any section | Always | OCR |
| `item_type` | Second line (천옷, 경갑옷, 양손 검, 액세서리) | Usually | OCR |
| `craftsman` | "N단 대장장이/재단사..." | Sometimes | OCR |
| `item_grade` | "등급" or "에픽"/"레어" standalone | Sometimes | OCR |
| `grade_bonus` | "등급 보너스 대미지..." | Sometimes | OCR |
| `item_attrs` | "아이템 속성" header | Always | OCR |
| `enchant` | "인챈트" header | Sometimes | OCR |
| `item_mod` | "개조" header | Sometimes | OCR |
| `reforge` | "세공" header | Sometimes | OCR (DB-important) |
| `erg` | "에르그" header | Sometimes | OCR |
| `set_item` | "세트아이템" header | Sometimes | OCR |
| `item_color` | "아이템 색상" header | Usually | Structural parse (no OCR) |
| `flavor_text` | After item_color, before price | Usually | Skip |
| `shop_price` | "상점판매가" | Usually | Skip |

## Section Detection Strategy

Two visual styles exist for section headers:

**Style A — Box borders** (lobe, captain_suit, lightarmor):
- Visual: `ㄱ 아이템 속성 ㅡㅡㅡㅡ` with `ㄴㅡㅡㅡㅡㅡㅡ` at bottom
- After our border filter, the header text is cropped to just "아이템 속성"
- Detection: OCR the header line, match against known section names

**Style B — Dash borders** (titan_blade, dropbell):
- Visual: `- 아이템 속성 -` or `- 인챈트 -`
- Detection: OCR the header line, match against known section names

**Detection approach:** After splitting all lines and running OCR on each, match OCR text against a list of known section header patterns. The parser doesn't need to visually detect headers — it uses OCR text matching.

This is robust because:
- Section headers are short, distinctive text (high OCR accuracy even now)
- The patterns are finite and well-defined
- Works regardless of visual style (box borders vs dashes)

## Horizontal Splitting

Already implemented in `_add_line()` (gap > `line_h * 3`). The parser groups sub-lines by y-position and:
- For `item_color` section: parses structurally (`파트 X`, `R:N`, `G:N`, `B:N`)
- For other sections: concatenates OCR text with spaces

## Config Format (`configs/mabinogi_tooltip.yaml`)

```yaml
game: mabinogi
version: 1

sections:
  item_name:
    order: 1
    header: null  # No header, always first line(s)
    required: true
    ocr: true

  item_type:
    order: 2
    header: null  # No header, identified by position
    required: false
    ocr: true

  item_attrs:
    order: 10
    header_patterns:
      - "아이템 속성"
    required: true
    ocr: true

  enchant:
    order: 20
    header_patterns:
      - "인챈트"
    required: false
    ocr: true

  item_mod:
    order: 30
    header_patterns:
      - "개조"
    required: false
    ocr: true

  reforge:
    order: 40
    header_patterns:
      - "세공"
    required: false
    ocr: true

  erg:
    order: 50
    header_patterns:
      - "에르그"
    required: false
    ocr: true

  set_item:
    order: 60
    header_patterns:
      - "세트아이템"
    required: false
    ocr: true

  item_color:
    order: 70
    header_patterns:
      - "아이템 색상"
    required: false
    ocr: false  # Structural parse instead
    parse_mode: color_parts

  flavor_text:
    order: 80
    header: null  # Lines after item_color that aren't price
    required: false
    skip: true

  shop_price:
    order: 90
    header_patterns:
      - "상점판매가"
    required: false
    skip: true
```

## Implementation Steps

### Step 1: Create config file
`configs/mabinogi_tooltip.yaml` with section definitions as above.

### Step 2: Create `MabinogiTooltipParser`
`backend/lib/mabinogi_tooltip_parser.py`:

```python
class MabinogiTooltipParser(TooltipLineSplitter):
    def __init__(self, config_path, output_dir="split_output"):
        super().__init__(output_dir)
        self.config = load_config(config_path)

    def parse_tooltip(self, image_path, reader):
        """Full pipeline: split → OCR → categorize → structure."""
        img, gray, binary = self.preprocess_image(image_path)
        detected_lines = self.detect_text_lines(binary)

        # Group sub-lines by y-position (horizontal splits)
        grouped_lines = self._group_by_y(detected_lines)

        # OCR each line/sub-line
        ocr_results = self._ocr_lines(img, grouped_lines, reader)

        # Categorize into sections
        sections = self._categorize_sections(ocr_results)

        return sections

    def _group_by_y(self, lines):
        """Group horizontally-split sub-lines by shared y-position."""
        ...

    def _ocr_lines(self, img, grouped_lines, reader):
        """Run OCR on each line, joining sub-line results."""
        ...

    def _categorize_sections(self, ocr_results):
        """Match OCR text against section header patterns."""
        ...

    def _parse_color_parts(self, sub_lines):
        """Structurally parse color part sub-lines."""
        # Each color part splits into 4 segments: "파트 X", "R:N", "G:N", "B:N"
        ...
```

### Step 3: Update `backend/main.py`
Replace `TooltipLineSplitter` with `MabinogiTooltipParser`. Return structured response:

```json
{
  "filename": "item.png",
  "sections": {
    "item_name": {"text": "축복받은 파멸의 로브(남성용)", "lines": [...]},
    "item_attrs": {"lines": [
      {"text": "방어력 0", "confidence": 0.56},
      {"text": "보호 1", "confidence": 0.57}
    ]},
    "item_color": {"parts": [
      {"part": "A", "r": 0, "g": 0, "b": 12},
      {"part": "B", "r": 0, "g": 0, "b": 0}
    ]},
    "enchant": null,
    "reforge": null
  },
  "skipped": ["flavor_text", "shop_price"]
}
```

### Step 4: Update test script
`scripts/test_v2_pipeline.py` — handle grouped lines for GT comparison, report section detection accuracy.

## What This Does NOT Change

- `TooltipLineSplitter` base class — stays generic
- OCR model / training pipeline — no changes
- Training data generation — no changes
- `ocr_utils.py` inference patch — stays as-is

## Deferred (needs more tooltip samples)

- Pre-header lines detection (item_name, item_type, craftsman) — needs visual position rules, not just text matching
- Subsection detection within enchant (접두 vs 접미) — needs OCR text parsing after section categorization
- `item_grade` detection (에픽/레어 standalone vs 등급 header) — varies by item type
- Fine-tuning header matching thresholds — may need fuzzy matching since OCR isn't perfect on headers yet

The user mentioned they'll provide more tooltip images. Once available, we can refine the detection rules and handle edge cases.
