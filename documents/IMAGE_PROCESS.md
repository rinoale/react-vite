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
| RGB to HSV | [—] | Separates hue/saturation/value — easier color range selection (e.g., "all reds"). |
| RGB to LAB | [—] | Perceptually uniform — Euclidean distance = perceived color difference. |
| RGB to YCrCb | [—] | Separates luminance (Y) from chrominance — used in skin/text detection. |
| Color quantization | [—] | Reduce image to N representative colors (k-means on pixel values). |
| Histogram equalization | [—] | Spread pixel intensity distribution to improve contrast. |
| CLAHE | [—] | Contrast-Limited Adaptive Histogram Equalization — local contrast enhancement. |

**Project usage**:
- Orange mask `(r>150) & (50<g<180) & (b<80)` for section header detection in `tooltip_segmenter.py`
- White balance mask `(max_ch>150) & (ratio<1.4)` for enchant text in `mabinogi_tooltip_parser.py` (oreo_flip)
- Pure-white mask `(r>=T) & (g>=T) & (b>=T)` explored for enchant header isolation

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
