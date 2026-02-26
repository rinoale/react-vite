# Image Processing Techniques Reference

Comprehensive reference of image processing techniques for OCR and document analysis.
Each technique is marked with its usage status in this project.

Legend: **[USED]** = actively used in this project, **[—]** = not used

---

## 1. Grayscale Conversion

| Technique | Status | Description |
|-----------|--------|-------------|
| BT.601 weighted | **[USED]** | `0.299R + 0.587G + 0.114B` — standard video formula, green-weighted. `cv2.cvtColor(BGR2GRAY)` uses this. |
| BT.709 weighted | [—] | `0.2126R + 0.7152G + 0.0722B` — HDTV standard, heavier green weight. |
| Equal weight | [—] | `(R + G + B) / 3` — simple average, no perceptual weighting. |
| Luminance (L channel) | [—] | Extract L from CIE LAB color space — perceptually uniform brightness. |
| Desaturation | [—] | `(max(R,G,B) + min(R,G,B)) / 2` — midpoint of channel extremes. |
| Single channel | [—] | Use only one channel (e.g., green for best text contrast). |

**Project usage**: `cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)` in `tooltip_line_splitter.py`, `mabinogi_tooltip_parser.py`, `tooltip_segmenter.py`

---

## 2. Thresholding

| Technique | Status | Description |
|-----------|--------|-------------|
| Global fixed threshold | **[USED]** | Single threshold for entire image. `cv2.threshold(gray, T, 255, type)` |
| THRESH_BINARY | **[USED]** | Pixels > T → 255, else → 0. Used for dark background images. |
| THRESH_BINARY_INV | **[USED]** | Pixels > T → 0, else → 255. Used for light background (black text on white). |
| Otsu's method | [—] | Automatically finds optimal threshold by minimizing intra-class variance. |
| Adaptive (mean) | [—] | Per-pixel threshold = mean of local neighborhood. Handles uneven lighting. |
| Adaptive (Gaussian) | [—] | Per-pixel threshold = Gaussian-weighted sum of neighborhood. Smoother than mean. |
| Niblack | [—] | `T = mean + k * std_dev` per window. Good for degraded documents. |
| Sauvola | [—] | Improved Niblack: `T = mean * (1 + k * (std_dev / R - 1))`. Better for mixed backgrounds. |
| Multi-level (Ternary) | [—] | Three output levels instead of two — separate strong/weak/background. |

**Project usage**: Fixed threshold=80 for content OCR, threshold=50 for header OCR. Both `BINARY` and `BINARY_INV` depending on background polarity detection.

---

## 3. Color Masking & Color Space

| Technique | Status | Description |
|-----------|--------|-------------|
| Per-channel RGB threshold | **[USED]** | `(R > a) & (G > b) & (B < c)` — isolate colors by channel ranges. |
| Channel balance ratio | **[USED]** | `max(R,G,B) / min(R,G,B)` — detect balanced (white/gray) vs colored pixels. |
| RGB to HSV | **[USED]** | Separates hue/saturation/value — easier color range selection (e.g., "all reds"). |
| RGB to LAB | [—] | Perceptually uniform — Euclidean distance = perceived color difference. |
| RGB to YCrCb | [—] | Separates luminance (Y) from chrominance — used in skin/text detection. |
| Color quantization | [—] | Reduce image to N representative colors (k-means on pixel values). |
| Histogram equalization | [—] | Spread pixel intensity distribution to improve contrast. |
| CLAHE | [—] | Contrast-Limited Adaptive Histogram Equalization — local contrast enhancement. |

**Project usage**:
- Orange mask `(r>150) & (50<g<180) & (b<80)` for section header detection in `tooltip_segmenter.py`
- White balance mask `(max_ch>150) & (ratio<1.4)` for enchant text in `mabinogi_tooltip_parser.py` (oreo_flip)
- Pure-white mask `(r>=T) & (g>=T) & (b>=T)` explored for enchant header isolation
- HSV hue rejection for blue text in nanum_gothic pre_header preprocessing (see §3.1)

---

### 3.1 HSV Hue Rejection — Removing Anti-Aliased Blue Text

**Problem**: The pre_header region contains both white/yellow text (item name, enchant names) and blue text (UI descriptions). When applying BT.601 grayscale + threshold 80 for NanumGothicBold preprocessing, the blue text and all its anti-aliased (AA) fringe pixels survive the threshold, creating ghost lines in OCR.

**Why RGB-based rejection fails**: Anti-aliasing creates a smooth gradient from the core blue color down to the dark background. These fringe pixels have intermediate RGB values that don't match the original blue color within any reasonable tolerance. Attempts tried and failed:

| Approach | Problem |
|----------|---------|
| Exact color match (tolerance=40) | Only catches core pixels. AA fringes at e.g. `(146,126,157)` are 80+ away from the blue center `(190,204,254)`. |
| Blue-dominant heuristic (`B > R+30`) | Margin too strict for dimmer fringes. Some AA pixels like `(131,100,125)` have R > B despite being blue text residue. |
| Increasing tolerance | Risky — `(190,204,254)` is close to white `(255,255,255)`, so high tolerance starts matching white text. |

**Solution — HSV hue rejection**: Convert to HSV color space and reject by hue angle. HSV separates color identity (hue) from brightness (value) and intensity (saturation), so all shades of blue — from bright core to dim AA fringe — share the same hue range.

```
HSV color wheel (OpenCV 0-180 range):
  H=0-15     Red
  H=15-35    Yellow      ← item name text (H≈29)
  H=105-135  Blue        ← blue UI text core (H≈113)
  H=135-165  Purple      ← blue text AA fringes
```

**Implementation** (`v3_pipeline.py` → `_preprocess_nanum_gothic()`):
```python
hsv = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2HSV)
h = hsv[:, :, 0]
blue_mask = (h >= 105) & (h <= 165)  # blue + purple AA fringes
masked = content_bgr.copy()
masked[blue_mask] = 0                # set to black → below threshold 80
```

**Measured result on `predator_simple_fhd_ng_original.png`**:

| Hue range | Pixel count | Above BT.601>80 | Category |
|-----------|-------------|------------------|----------|
| H=15-35 (yellow) | 837 | 837 | Item name text — KEPT |
| H=105-135 (blue) | 828 | 828 | Blue UI text — REJECTED |
| H=135-165 (purple) | 247 | 244 | Blue AA fringes — REJECTED |

Eliminated all 4 blue ghost lines down to 0, while preserving the 1 legitimate item name line.

**Why this works and RGB doesn't**: In RGB, a dim blue AA pixel `(80, 65, 90)` looks nothing like bright blue `(190, 204, 254)` — they're far apart in Euclidean distance. But in HSV, both map to H≈120 (blue hue). The hue angle is invariant to brightness and saturation changes that anti-aliasing produces.

### 3.2 What Is Hue?

Hue is the **angle on the color wheel** — it answers "what color is this?" regardless of brightness or saturation.

```
        Red (0°)
         |
Purple   |   Orange
  \      |      /
   \     |     /
    Blue--+--Yellow
   /     |     \
  /      |      \
Cyan     |   Green
       (180°)
```

It is **not** a ratio. It is computed from which RGB channel is dominant and by how much:

- R is highest → hue is between Yellow and Purple (0°/360° side)
- G is highest → hue is between Yellow and Cyan (60°-180°)
- B is highest → hue is between Cyan and Purple (180°-300°)

Formula (simplified, when R is max):
```
H = 60° × (G - B) / (max - min)
```

**Example** — blue text `RGB(74, 149, 238)`:
- B is max (238), min is R (74)
- H = 60 × (R-G)/(max-min) + 240 = 60 × (74-149)/(238-74) + 240 = **213°**
- OpenCV halves it → **H ≈ 106**

Its dim AA fringe `RGB(37, 75, 119)`:
- Same dominant channel (B), same proportions → **H ≈ 106**

The angle stays the same as pixels get dimmer through anti-aliasing because the proportions between channels are preserved, just scaled down toward black.

### 3.3 Applying HSV Hue Rejection to Other Colors

HSV hue rejection works for **any color**, not just blue. Pick the hue range for the target:

| Target color | Hue range to reject (OpenCV) | Would preserve |
|---|---|---|
| Blue text | H=105-165 | Yellow, white, red, green |
| Red text | H=0-15 + H=165-180 (wraps around 0) | Blue, yellow, green |
| Green text | H=35-85 | Blue, yellow, red, white |
| Orange text | H=10-25 | Blue, white, purple |

**White and black are immune**: white has near-zero saturation (S≈0), so its hue is undefined and won't match any hue range. Black has near-zero value (V≈0). Neither gets accidentally rejected.

**When to use HSV vs RGB**:

| Situation | Best approach |
|---|---|
| Isolate a specific known color (e.g. white ±5) | RGB exact match — precise |
| Reject a color **and all its AA fringes** | HSV hue — catches the full gradient |
| Separate warm vs cool colors broadly | HSV hue — one threshold splits the wheel |
| Match multiple shades of "blue" without listing each | HSV hue — single range covers all |

### 3.4 ELI5: HSV Hue Rejection

HSV hue rejection is like sorting M&Ms by color.

**The problem:** You have a picture with blue text you want to remove. But the edges of the text are blurry — they're not pure blue, they're dim, faded blue mixed with the dark background. If you try to match the exact blue color (RGB), you miss all these blurry edge pixels because their RGB numbers look completely different.

**The insight:** Every color has three properties:
- **Hue** — *what* color it is (blue, red, yellow...)
- **Saturation** — how vivid it is (bright blue vs grayish blue)
- **Value** — how bright it is (bright blue vs dark blue)

A bright blue pixel and a dim, faded blue pixel have totally different brightness — but they're both **blue**. Their hue is the same.

**Hue is like a compass pointing to a color.** It's an angle on a color wheel (0-360°):
- 0° = Red
- 60° = Yellow
- 120° = Green
- 240° = Blue
- 300° = Purple

No matter how bright or dim the pixel is, the compass still points to "blue" (around 240°).

**The solution:** Instead of asking "is this pixel exactly RGB(74,149,238)?", ask "does this pixel's hue point to blue?" — That catches the bright blue text AND all the dim, faded edge pixels in one sweep.

In the pipeline, we reject everything from 210° to 330° (blue through purple). Four ghost lines of blue text — gone.

---

## 4. Morphological Operations

| Technique | Status | Description |
|-----------|--------|-------------|
| Erosion | [—] | Shrinks foreground — removes small noise, thins text strokes. |
| Dilation | [—] | Expands foreground — fills gaps, connects broken strokes. |
| Opening (erode → dilate) | [—] | Removes small noise while preserving object size. |
| Closing (dilate → erode) | [—] | Fills small holes/gaps while preserving object size. |
| Morphological gradient | [—] | `dilation - erosion` — extracts object boundaries. |
| Top-hat | [—] | `original - opening` — extracts bright features smaller than kernel. |
| Black-hat | [—] | `closing - original` — extracts dark features smaller than kernel. |
| Skeletonization | [—] | Reduces objects to 1-pixel-wide skeleton while preserving topology. |
| Hit-or-miss | [—] | Template matching on binary images — detect specific pixel patterns. |

**Project usage**: None currently. Explored during enchant header investigation (dilate pure-white mask to fill characters) but abandoned — strokes too thin at 10-11px for morphological recovery.

---

## 5. Filtering & Noise Removal

| Technique | Status | Description |
|-----------|--------|-------------|
| Gaussian blur | [—] | Weighted average using Gaussian kernel — smooths noise, reduces detail. |
| Median filter | [—] | Replaces each pixel with median of neighborhood — excellent for salt-and-pepper noise. |
| Bilateral filter | [—] | Smooths while preserving edges — uses both spatial and intensity distance. |
| Box filter (mean) | [—] | Simple average of neighborhood pixels — fast but blurs edges. |
| Non-local means | [—] | Averages similar patches across entire image — best denoising but slow. |
| Sharpening (unsharp mask) | [—] | `original + k * (original - blurred)` — enhances edges and fine detail. |
| Wiener filter | [—] | Optimal filter for additive noise — minimizes mean square error. |

**Project usage**: None. Training data uses clean binary images (no augmentation by design). Real crops are binary after thresholding.

---

## 6. Edge Detection

| Technique | Status | Description |
|-----------|--------|-------------|
| Canny | [—] | Multi-stage: Gaussian → gradient → non-max suppression → hysteresis. Gold standard. |
| Sobel | [—] | First derivative in x/y direction — gives gradient magnitude and direction. |
| Laplacian | [—] | Second derivative — detects edges as zero-crossings. Sensitive to noise. |
| Prewitt | [—] | Similar to Sobel with different kernel weights. |
| Scharr | [—] | Improved Sobel with better rotational symmetry for 3x3 kernels. |
| Roberts cross | [—] | 2x2 diagonal gradient — fast but noise-sensitive. |

**Project usage**: None. Line detection uses projection profiling instead of edge detection — more reliable for structured tooltip layouts.

---

## 7. Projection Profiling

| Technique | Status | Description |
|-----------|--------|-------------|
| Horizontal projection | **[USED]** | Sum pixels per row → detect text lines as peaks, gaps as valleys. |
| Vertical projection | **[USED]** | Sum pixels per column → detect character/word boundaries. |
| Gap tolerance | **[USED]** | Close small gaps (≤N rows) in projection to handle thin stroke dips. |
| Run-length encoding | **[USED]** | Track contiguous runs of active/inactive rows for band detection. |
| Local projection | **[USED]** | Projection within a sub-region for splitting merged blocks. |
| Density thresholding | **[USED]** | Filter by pixel density per row/column to separate text from borders. |

**Project usage**: Core technique for line splitting in `tooltip_line_splitter.py`. Also used for orange band detection in `tooltip_segmenter.py` and white-pixel band detection in enchant header processing.

---

## 8. Segmentation

| Technique | Status | Description |
|-----------|--------|-------------|
| Connected components | **[USED]** | Label distinct objects — each connected region gets unique ID. |
| Contour detection | [—] | `cv2.findContours()` — trace object boundaries. Useful for character isolation. |
| Watershed | [—] | Treats image as topographic surface — flood-fills from markers to segment touching objects. |
| Distance transform | [—] | Each foreground pixel = distance to nearest background. Useful as watershed marker. |
| Region growing | [—] | Start from seed points, grow regions by adding similar neighbors. |
| Flood fill | [—] | Fill connected region of similar pixels from seed point. |
| GrabCut | [—] | Iterative foreground/background segmentation using graph cuts. |
| Superpixels (SLIC) | [—] | Over-segment image into perceptually meaningful atomic regions. |

**Project usage**: `cv2.connectedComponentsWithStats()` in `find_black_squares.py` for header boundary detection.

---

## 9. Geometric Transforms

| Technique | Status | Description |
|-----------|--------|-------------|
| Resize (INTER_AREA) | **[USED]** | Downscale with pixel area averaging — best for shrinking without aliasing. |
| Resize (INTER_NEAREST) | **[USED]** | Nearest-neighbor — preserves pixel-exact values, used for debug visualization. |
| Resize (BICUBIC/LANCZOS) | **[USED]** | Smooth interpolation — used in EasyOCR's AlignCollate during inference. |
| Affine transform | [—] | 2D linear: translate, rotate, scale, shear. Preserves parallel lines. |
| Perspective transform | [—] | 3D projection correction (4-point mapping). Fixes keystoning from angled capture. |
| Deskewing | [—] | Detect text angle (via Hough lines or projection) → rotate to horizontal. |
| Rotation | [—] | Simple angular rotation around center point. |
| Flipping | [—] | Mirror horizontally or vertically. |
| Cropping | **[USED]** | Extract rectangular sub-region. Core operation for line/header crops. |
| Tight-crop to ink | **[USED]** | Find bounding box of non-white pixels and crop to that + padding. |

**Project usage**: `INTER_AREA` for training data downscale. `INTER_NEAREST` for debug zoom. `BICUBIC` in EasyOCR AlignCollate. Cropping is fundamental throughout.

---

## 10. Bitwise Operations

| Technique | Status | Description |
|-----------|--------|-------------|
| bitwise_not | **[USED]** | Invert all bits — swap foreground/background. |
| bitwise_and | [—] | Pixel-wise AND — apply mask to extract region. |
| bitwise_or | [—] | Pixel-wise OR — combine masks. |
| bitwise_xor | [—] | Pixel-wise XOR — find differences between two binary images. |

**Project usage**: `cv2.bitwise_not()` for polarity inversion in oreo_flip and line detection.

---

## 11. Feature Detection

| Technique | Status | Description |
|-----------|--------|-------------|
| Harris corner detection | [—] | Detect corner points via eigenvalue analysis of gradient matrix. |
| Shi-Tomasi corners | [—] | Improved Harris — `min(eigenvalue1, eigenvalue2) > threshold`. |
| SIFT | [—] | Scale-invariant keypoints with 128-dim descriptors. Robust but patented (now free). |
| SURF | [—] | Faster SIFT approximation using box filters. |
| ORB | [—] | Fast binary descriptor — combines FAST keypoints + BRIEF descriptors. |
| Hough line transform | [—] | Detect straight lines in edge maps — useful for deskewing, table detection. |
| Hough circle transform | [—] | Detect circles — useful for bullet points, UI elements. |
| Template matching | [—] | Slide a template across image, measure similarity at each position. |

**Project usage**: None. Structured tooltip layout doesn't need feature detection.

---

## 12. Frequency Domain

| Technique | Status | Description |
|-----------|--------|-------------|
| FFT (Fast Fourier Transform) | [—] | Decompose image into frequency components — low freq = smooth, high freq = edges. |
| Inverse FFT | [—] | Reconstruct image from frequency domain after filtering. |
| DCT (Discrete Cosine Transform) | [—] | Real-valued frequency transform — used in JPEG compression. |
| High-pass filter (freq) | [—] | Remove low frequencies → enhance edges and text strokes. |
| Low-pass filter (freq) | [—] | Remove high frequencies → smooth noise while keeping structure. |
| Band-pass filter | [—] | Keep only specific frequency range — isolate periodic patterns. |
| Notch filter | [—] | Remove specific frequency (e.g., moire pattern from screen capture). |

**Project usage**: None. Binary thresholded images don't benefit from frequency analysis.

---

## 13. Text-Specific Techniques

| Technique | Status | Description |
|-----------|--------|-------------|
| CRAFT text detection | [—] | Deep learning model for natural scene text localization. EasyOCR uses it by default. |
| Line splitting via projection | **[USED]** | Horizontal projection profiling to split text into individual lines. |
| Horizontal sub-splitting | **[USED]** | Vertical projection within a line to detect word/column gaps. |
| Border removal | **[USED]** | Detect and mask UI frame borders that interfere with text detection. |
| CTC decoding | **[USED]** | Connectionist Temporal Classification — sequence decoding for OCR output. No length constraint. |
| Fuzzy matching (FM) | **[USED]** | RapidFuzz post-processing against per-section dictionaries to correct OCR errors. |
| Beam search decoding | [—] | Alternative to greedy CTC — explores multiple candidate sequences. |
| Language model post-processing | [—] | Use n-gram or neural LM to constrain/correct OCR output. |
| Deskew via projection | [—] | Rotate image at multiple angles, pick angle with sharpest projection peaks. |
| Binarization quality metrics | [—] | PSNR, F-measure, NRM to evaluate binarization output quality. |

**Project usage**: Custom `TooltipLineSplitter` replaces CRAFT — better for structured game UI. TPS-ResNet-BiLSTM-CTC architecture. FM against enchant/reforge dictionaries.

---

## 14. Training Data Generation

| Technique | Status | Description |
|-----------|--------|-------------|
| Synthetic text rendering | **[USED]** | Render text with game fonts to generate training images. |
| Game-like rendering pipeline | **[USED]** | Dark bg → bright text → grayscale → threshold → tight-crop → downscale → re-threshold. |
| Quality gates | **[USED]** | Reject images failing ink ratio, dimension, or binary purity checks. |
| Random threshold variation | **[USED]** | Threshold 80 ± random(-10, +40) for training robustness. |
| Data augmentation (blur) | [—] | Apply Gaussian/motion blur to training images. |
| Data augmentation (noise) | [—] | Add Gaussian/salt-and-pepper noise. |
| Data augmentation (erode/dilate) | [—] | Randomly thin/thicken text strokes. |
| Data augmentation (rotation) | [—] | Small random rotations (±2-5 degrees). |
| Data augmentation (elastic) | [—] | Non-linear deformation to simulate real-world text distortion. |
| Style transfer | [—] | Transform synthetic images to look like real-world captures. |
| MixUp / CutMix | [—] | Blend training samples for regularization. |

**Project usage**: Clean binary only — no augmentation by design. Game renders pixel-perfect text, so augmentation would add unrealistic variation.

---

## 15. Deep Learning / Advanced

| Technique | Status | Description |
|-----------|--------|-------------|
| Super-resolution | [—] | Neural network upscaling of low-resolution text images. |
| Denoising autoencoder | [—] | Learn to reconstruct clean images from noisy input. |
| GAN-based restoration | [—] | Generate clean document images from degraded input (CycleGAN, Pix2Pix). |
| Diffusion model restoration | [—] | Iterative denoising for high-quality image restoration. |
| Attention mechanisms | [—] | Focus on relevant image regions during recognition (used in TPS). |
| TPS (Thin Plate Spline) | **[USED]** | Spatial transformer for text rectification — handles curved/distorted text. |
| ResNet feature extraction | **[USED]** | Deep residual network for extracting visual features from text images. |
| BiLSTM sequence modeling | **[USED]** | Bidirectional LSTM for contextual sequence prediction in OCR. |

**Project usage**: TPS-ResNet-BiLSTM-CTC architecture (from deep-text-recognition-benchmark). TPS handles spatial distortion, ResNet extracts features, BiLSTM models sequence context, CTC decodes output.

---

## V3 Pipeline — Preprocessing Per Stage

The V3 pipeline receives an **original color screenshot** (BGR) and applies different preprocessing depending on the pipeline stage.

### 1. Section Header OCR

Detects orange header text (e.g. 인챈트, 세공, 에르그) within black-square regions.

| Step | Technique | Detail |
|------|-----------|--------|
| Grayscale | BT.601 weighted (§1) | `cv2.cvtColor(BGR2GRAY)` |
| Threshold | Global fixed, BINARY_INV (§2) | threshold=50 (configurable via yaml) |

Code: `tooltip_segmenter.py` → `_preprocess_header()`

### 2. Pre-Header OCR

The pre_header region (above the first orange header) contains item name, enchant prefix/suffix names, and holywater effects. Two preprocessing paths run in parallel; the higher-confidence result per line wins.

**Path A — mabinogi_classic** (color mask):

| Step | Technique | Detail |
|------|-----------|--------|
| Color mask | Exact RGB match (§3) | Match white `(255,255,255)` and yellow `(255,252,157)` ±5 tolerance |
| Invert | bitwise_not (§10) | White mask → black-on-white for OCR |

**Path B — nanum_gothic** (BT.601 + blue rejection):

| Step | Technique | Detail |
|------|-----------|--------|
| Blue rejection | HSV hue rejection (§3.1) | Reject H=105-165 (blue+purple) → set to black |
| Grayscale | BT.601 weighted (§1) | `cv2.cvtColor(BGR2GRAY)` on blue-rejected image |
| Threshold | Global fixed, BINARY_INV (§2) | threshold=80 |

The winning preprocessing per line also determines which font the tooltip uses, enabling single-model routing for content segments (future optimization).

Code: `v3_pipeline.py` → `_step_pre_header()`, `_preprocess_mabinogi_classic()`, `_preprocess_nanum_gothic()`

### 3. Content OCR

General text recognition for all non-enchant content sections (item stats, description, reforge, etc.)

| Step | Technique | Detail |
|------|-----------|--------|
| Grayscale | BT.601 weighted (§1) | `cv2.cvtColor(BGR2GRAY)` |
| Threshold | Global fixed, BINARY_INV (§2) | threshold=80 |

Code: `mabinogi_tooltip_parser.py` → `_parse_segment()`

### 3. Enchant Slot Header OCR

Isolates white enchant slot header text (e.g. `[접두] 창백한 (랭크 A)`) from colored effect text on any background theme.

| Step | Technique | Detail |
|------|-----------|--------|
| Color mask | Channel balance ratio (§3) | `max(R,G,B) > 150` AND `max/min ratio < 1.4` — keeps balanced bright pixels (white/gray), rejects colored pixels (orange, blue, pink) |
| Border strip | Density thresholding (§7) | Edge columns with >50% white density are cleared |
| Invert | bitwise_not (§10) | White mask → black-on-white for OCR |

Code: `mabinogi_tooltip_parser.py` → `_oreo_flip()`

### 4. Header Detection (non-OCR)

Locates section header positions in the screenshot using orange text color. Not OCR — just spatial detection.

| Step | Technique | Detail |
|------|-----------|--------|
| Color mask | Per-channel RGB threshold (§3) | `R>150, 50<G<180, B<80` — orange text mask |
| Projection | Horizontal projection + run-length (§7) | Detect orange bands → filter by height and pixel count |
| Boundary | Connected components (§8) | Near-black boundary expansion around orange bands |

Code: `tooltip_segmenter.py` → `detect_headers()`

### 5. Border Detection (non-OCR)

Detects tooltip frame borders to constrain content regions. Not OCR — spatial boundary detection.

| Step | Technique | Detail |
|------|-----------|--------|
| Color mask | Per-channel RGB threshold (§3) | RGB(132,132,132) ±5 tolerance |
| Bottom | Density thresholding (§7) | Scan rows bottom→up, first row with ≥30% border pixels |
| Left/Right | Density thresholding (§7) | Scan columns inward from each edge |

Code: `tooltip_segmenter.py` → `detect_bottom_border()`, `detect_vertical_borders()`
