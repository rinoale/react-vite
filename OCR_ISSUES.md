# OCR Pipeline Issues

## Resolved

- **Incomplete Character Set** — Expanded from 342 to 442 characters covering all ground truth text. Added missing digits, punctuation, and 79 Korean characters.
- **Training Data Too Narrow** — Created `tooltip_general.txt` (453 entries) covering UI labels, item types, enchants, stats, descriptions. Combined with `reforging_options.txt` for 3,714 training samples.
- **Line Splitter Fails on Preprocessed Images** — Added auto-detection of background polarity (light vs dark) with adaptive thresholding.
- **Poor Line Detection** — Replaced connected component approach with horizontal projection profiling. Line splitter now achieves perfect detection: 75/75 (lightarmor), 22/22 (lobe), 23/23 (captain suit).
- **Low OCR Confidence** — Retrained model with correct character set (99.246% accuracy on training data). Fixed critical `--sensitive` flag bug that silently dropped all Korean training samples.
- **PAD Mismatch** — Training without `--PAD` caused preprocessing mismatch vs EasyOCR inference (which always uses `keep_ratio_with_pad=True`). Fixed by adding `--PAD` flag.
- **Grayscale Domain Gap** — 78% of synthetic training images were grayscale anti-aliased while real images are binary (0/255 only). Fixed by enforcing 100% binary thresholding and re-thresholding after resize.
- **Line Splitter Border Artifacts** — Vertical UI border columns (1-2px wide, spanning many rows) bridged gaps between text lines, causing merges. Fixed with `_remove_borders()` that masks columns with >15% row density.
- **Line Splitter Padding Bleed** — Fixed 10px padding bled into adjacent lines for 10-12px tall text. Changed to proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`.
- **Missing Section Headers** — Horizontal separator removal was destroying "개조" and "세공" headers adjacent to box borders. Fixed by keeping horizontal separators (they don't bridge sections since they're single rows).
- **Short Text Filtered** — "천옷" (14px wide) was filtered by `min_width=30`. Reduced to `min_width=10`.

---

## Resolved (Architecture): CRAFT Detection Replaced

**Problem:** EasyOCR's CRAFT detector was fundamentally wrong for structured tooltip layouts. CRAFT is designed for natural scene text (signs, labels in photos) and caused:
- Line fragmentation: single lines split into 2-3 detection boxes
- Line merging: adjacent lines combined into one region
- Missed sections: entire enchant/reforging blocks skipped
- Irregular polygonal crops that don't match training data format

**Solution:** Replaced CRAFT with `TooltipLineSplitter` (horizontal projection profiling). The new v2 pipeline uses line splitting for detection and EasyOCR's `recognize()` API for recognition only. See `OCR_TRAINING_HISTORY.md` for full details.

---

## Current: Recognition Accuracy on Real Images

Despite 97-100% accuracy on synthetic training data across 6 attempts, the custom model still produces poor results on real preprocessed screenshots. Remaining domain gaps being investigated:

1. **Scale mismatch** — Real line crops have text at game font size (~10-12px), synthetic renders at random 12-26px. The model may not generalize across these scales.
2. **Aspect ratio / canvas width** — Real crops span full tooltip width (~250px) with text left-aligned. Synthetic width varies tightly around text length.
3. **Content patterns** — Training on individual dictionary words misses real tooltip patterns like `R:0 G:0 B:12`, `내구력 20/20`, `- 방어 20, 보호 15 차감`.

**Next steps:** Regenerate training data to closely match real line crop characteristics (dimensions, scale, content patterns) and retrain.
