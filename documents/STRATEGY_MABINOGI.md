# Strategy: Mabinogi OCR Pipeline

Design decisions specific to the Mabinogi tooltip OCR pipeline. Each entry records *why* a choice was made and what to revisit if porting to another game.

---

### D1 — Line splitting: horizontal projection instead of CRAFT

**Decision:** Use a custom horizontal projection profiler (`TooltipLineSplitter`) instead of the general-purpose CRAFT text detector bundled with EasyOCR.

**Why:**
CRAFT is trained on natural scene text (signs, storefronts, photos). On structured tooltip layouts it consistently:
- Fragments a single line into multiple bounding boxes
- Merges adjacent lines across narrow inter-line gaps
- Misses entire sections with low-contrast or sparse text

Horizontal projection profiling exploits the fact that tooltip text is arranged in horizontal rows with clear inter-line gaps. Summing ink pixels per row produces a reliable density profile; valleys in the profile are gaps between lines.

**Tradeoff:** The splitter is domain-specific. It assumes horizontal, left-to-right text with clear inter-line gaps. It would not work on arbitrary document layouts or curved/diagonal text.

**Porting guide:** The core algorithm transfers to any game with a similar fixed-layout tooltip structure. Parameters to re-tune for a new game:
- `min_height`, `max_height` — measure actual line heights in that game's tooltip screenshots
- `gap_tolerance` — increase if character strokes cause frequent line dips; decrease if lines are very close together
- Border removal threshold (`col_density > 0.15`, run ≤ 3px) — inspect column density profiles in the new images

---

### D2 — Line splitting parameters are empirically tuned to Mabinogi

**Decision:** `min_height=6`, `max_height=25`, `min_width=10`, `gap_tolerance=2`, `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`

**Why:**
These values were derived by measuring real Mabinogi tooltip line crops:
- Mabinogi text lines are 7–14px tall in tooltip screenshots at native resolution
- Inter-line gaps are consistently 4+ rows, so gap_tolerance=2 closes thin dips without merging separate lines
- The proportional padding formula matches the splitter output to the training image format

**Porting guide:** For a new game, start by running the splitter on sample screenshots and examining the detected line heights. Adjust `max_height` first (the most common failure mode is merged lines when max_height is too high).

---

### D3 — Border removal targets only narrow high-density columns

**Decision:** `_remove_borders()` masks only columns with >15% global density AND ≤3px width, applied to line detection only — not to the final crop images.

**Why:**
Earlier attempts masked all high-density columns globally. This destroyed text alignment columns: many Mabinogi lines share characters at the same horizontal positions (e.g., repeated `ㄴ` or `-` prefixes), creating columns with >15% density that are text, not borders.

Limiting to ≤3px width ensures only actual UI border pipes (which are always 1–2px) are removed.

**Porting guide:** Inspect column density profiles of your target game's screenshots. If the UI has thicker borders (e.g., 4–5px), raise the width threshold. If text alignment columns are being accidentally masked, lower the density threshold.

---

### D4 — Horizontal sub-splitting for multi-column lines

**Decision:** Lines with internal horizontal gaps wider than `line_height × split_factor` are split into sub-segments, each OCR'd separately.

**Why:**
Mabinogi's color part lines (`파트 A    R:187    G:153    B:85`) have large inter-column gaps that the model cannot reliably read as a single sequence. Sub-splitting gives the model short, clean crops.

Two split factors are used:
- `1.5` for the color section (very wide gaps between label and values)
- `3.0` default (conservative, only splits genuinely wide gaps)

**Porting guide:** If the target game has multi-column data lines, identify the typical gap width and tune `horizontal_split_factor` accordingly. Color/stat tables are the most common case.

---

### D5 — Color parts bypass OCR entirely

**Decision:** After sub-splitting, color part segments (`R:N`, `G:N`, `B:N`) are parsed by regex, not by the OCR model.

**Why:**
The format is perfectly predictable (`R:` followed by 0–255). OCR adds noise and failure modes where there is no ambiguity. Regex is 100% accurate on well-split crops.

**Porting guide:** Any game data field with a fixed format (numeric stats with known prefixes, HP/MP bars, etc.) is a candidate for regex parsing instead of OCR. Identify these fields first — they're free accuracy.

---

### D6 — Synthetic training data only (no real game crops)

**Decision:** All training images are generated synthetically using the actual game font rendered with PIL, not extracted from real screenshots.

**Why:**
- No labeled real data existed at project start
- Synthetic generation is fully controllable and reproducible
- The game font is available as a TTF file, so synthetic images can closely match real renders

**Tradeoff:** There is a rendering gap between PIL's font rasterization and the game engine's font renderer. The most visible symptom: the `-` dash character renders as 5px wide in PIL but only 2px wide in the game at the same apparent size. This causes consistent OCR errors on lines starting with `- `.

**Porting guide:** Obtain the target game's font file (TTF/OTF) from the game client. Verify that PIL's rendering of that font produces images visually similar to real screenshot crops — this is the most important validation step. If the gap is large, prioritize collecting real labeled crops early.

---

### D7 — No augmentation in training data

**Decision:** Training images are strictly binary (0 and 255). No blur, noise, erosion, dilation, or other augmentation is applied.

**Why:**
Initial attempts with augmentation produced ~25% faint or unreadable training images, because thin Korean character strokes (1–2px) disappear under even mild blur or erosion. The game images, after browser thresholding at 80, are already clean binary — training on augmented images introduced a domain gap rather than closing one.

**Porting guide:** If the target game's images are clean binary after preprocessing, skip augmentation. If they are grayscale or anti-aliased (e.g., the game renders smooth text), augmentation with mild blur may improve generalization.

---

### D8 — Tight-crop training images (not fixed canvas)

**Decision:** Each synthetic training image is cropped tightly to the ink bounds of the rendered text, with only proportional padding added (`pad_x = max(2, text_h//3)`, `pad_y = max(1, text_h//5)`).

**Why:**
Early training used a fixed 260px-wide canvas regardless of text length. The model learned to expect whitespace on the right side of every image, which caused hallucination of characters in empty regions of real crops.

Tight crops match what the splitter actually produces: the crop width reflects the text content width.

**Porting guide:** Always match the training image format to the splitter output format. Measure the actual width distribution of real line crops from the target game's screenshots, then match that distribution in synthetic image generation.

---

### D9 — Font sizes are fixed to match real line heights

**Decision:** Training renders text only at font sizes `[10, 10, 10, 11, 11, 11]`, producing a height distribution centered at 14–15px.

**Why:**
Smaller sizes (6–7px) produce illegible crops that don't match real game lines. Larger sizes shift the height distribution away from what the splitter produces from real screenshots.

The 3:3 ratio of size-10 to size-11 was chosen to produce a unimodal distribution at h=14–15px, which reflects the dominant line height in Mabinogi tooltips.

**Porting guide:** Sample real line crops from the target game, measure their height distribution, then pick font sizes that reproduce that distribution. Do not resize synthetic images to a target height before training — let the model handle the resize via imgH normalization.

---

### D10 — Fixed imgW with inference patch

**Decision:** The model is trained with `imgW=200`. EasyOCR's runtime dynamic imgW computation (`ceil(w/h) * 32`) is monkey-patched to use the yaml value instead.

**Why:**
EasyOCR computes a per-image dynamic imgW during inference, which produces values of 576–1056px for typical line crops — completely mismatching the training imgW=200. The TPS spatial transformer is built with `I_size=(imgH, imgW)` and produces garbage output when the input size differs from training.

The patch is in `backend/ocr_utils.py` and must be applied after `easyocr.Reader()` is initialized.

**Porting guide:** Always verify that inference imgW matches training imgW before evaluating accuracy. This mismatch is silent — the model produces output but it will be garbage. Check `ocr_utils.py` is applied in any new inference script.
