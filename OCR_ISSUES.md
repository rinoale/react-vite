# OCR Pipeline Issues

## Resolved

- **Incomplete Character Set** — Expanded from 342 to 442 characters covering all ground truth text. Added missing digits, punctuation, and 79 Korean characters.
- **Training Data Too Narrow** — Created `tooltip_general.txt` (453 entries) covering UI labels, item types, enchants, stats, descriptions. Combined with `reforging_options.txt` for 3,714 training samples.
- **Line Splitter Fails on Preprocessed Images** — Added auto-detection of background polarity (light vs dark) with adaptive thresholding.
- **Poor Line Detection** — Replaced connected component approach with horizontal projection profiling. Also updated backend to use EasyOCR's CRAFT detector directly on full images, bypassing the line splitter entirely.
- **Low OCR Confidence** — Retrained model with correct character set (99.246% accuracy on training data). Fixed critical `--sensitive` flag bug that silently dropped all Korean training samples.

---

## Current: Font Domain Gap

The model achieves 99.2% accuracy on synthetic training data but performs poorly on real game screenshots. The training data is rendered with standard system fonts (via Pillow), while actual Mabinogi tooltips use the game's own pixel font at a specific size.

Some text is recognized correctly ("최대생명력 25 증가", "윈드밀 대미지", "불 속성", "표면 강화"), but most results are wrong or fragmented.

**Goal:** Generate training data using the actual Mabinogi game font (or a visually close substitute) to close the domain gap between synthetic and real images.

---

## Current: CRAFT Text Detection Fragmentation

EasyOCR's CRAFT detector splits tooltip text into many small regions rather than clean full lines. For example, a single line like "크리티컬 대미지 배율(19/20 레벨)" may be split into 2-3 separate detection boxes.

**Goal:** Either fine-tune CRAFT detection parameters for this use case, or post-process adjacent detection boxes to merge them back into full lines before recognition.
