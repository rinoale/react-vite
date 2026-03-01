# OCR Models

All models use `TPS-ResNet-BiLSTM-CTC` architecture (`imgH=32`, `hidden_size=256`).

## Model Inventory

| Model | Version | Chars | imgW | Font | Purpose | Last Updated |
|-------|---------|-------|------|------|---------|--------------|
| Content (mabinogi_classic) | a19 | 554 | 200 | mabinogi_classic.ttf | Font-specific content OCR | 2026-02-23 |
| Content (NanumGothicBold) | a19 | 554 | 200 | NanumGothicBold.ttf | Font-specific content OCR | 2026-02-23 |
| Category Header | v1 | 21 | 128 | (real crops) | 9-label section recognition | 2026-02-23 |
| Enchant Header | v3 | 626 | 256 | synthetic + real | Slot header + rank OCR | 2026-02-25 |
| Preheader (mabinogi_classic) | v1 | 1,181 | 200 | mabinogi_classic.ttf | Item name region OCR | 2026-02-27 |
| Preheader (NanumGothicBold) | v1 | 1,181 | 200 | NanumGothicBold.ttf | Item name region OCR | 2026-02-27 |
| Legacy Content (rollback) | a18 | 554 | 200 | both fonts mixed | Combined content OCR | 2026-02-23 |

## Current Performance

128/303 exact (42.2%), 70.2% char accuracy, FM=56 across 7 GT images.

**Key wins:**
- Double-dip resize fix (+37 exact, no retraining)
- Enchant v3 real-sample mixing (46.3% → 100% on enchant headers)
- Dual-form FM matching (FM 49 → 56)

**Known issues:** `등급` → `개조` header misread (~5%), leading `-` misread as `소`/`#`, ink ratio gap (real 0.201 vs synthetic 0.144).

---

## Model Details

### 1. Content — mabinogi_classic (a19)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/general_mabinogi_classic_model/a19/` |
| Symlink | `backend/ocr/models/custom_mabinogi_classic.*` |
| Charset | 554 chars (`unique_chars.txt`) |
| imgW | 200 (fixed via `ocr_utils.py` patch) |
| Font | `data/fonts/mabinogi_classic.ttf` |
| Training | 10,000 iterations, batch 64, lr default (Adadelta) |
| Training data | Synthetic (game-like rendering pipeline) |
| Deploy | `bash scripts/ocr/general_mabinogi_classic_model/deploy.sh a19` |
| Last updated | 2026-02-23 |

Mabinogi uses two fonts for tooltip text. This model handles lines rendered in the `mabinogi_classic` font. Part of the DualReader pair — both font-specific models run on every line, highest confidence wins.

### 2. Content — NanumGothicBold (a19)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/general_nanum_gothic_bold_model/a19/` |
| Symlink | `backend/ocr/models/custom_nanum_gothic_bold.*` |
| Charset | 554 chars (`unique_chars.txt`) |
| imgW | 200 (fixed via `ocr_utils.py` patch) |
| Font | `data/fonts/NanumGothicBold.ttf` |
| Training | 10,000 iterations, batch 64, lr default (Adadelta) |
| Training data | Synthetic (game-like rendering pipeline) |
| Deploy | `bash scripts/ocr/general_nanum_gothic_bold_model/deploy.sh a19` |
| Last updated | 2026-02-23 |

The other half of the DualReader pair. Same architecture, charset, and imgW as the mabinogi_classic model but trained exclusively on NanumGothicBold-rendered images.

### 3. Category Header (v1)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/category_header_model/v1/` |
| Symlink | `backend/ocr/models/custom_header.*` |
| Charset | 21 chars (`unique_chars.txt`) |
| imgW | 128 |
| Font | N/A (trained on real header crops) |
| Training | 10,000 iterations, batch 32 |
| Training data | Real crops from 9 screenshots (81 crops total) |
| Deploy | Manual copy + symlink update |
| Last updated | 2026-02-23 |

Recognizes the 9 section header labels that appear in orange text on Mabinogi tooltips:
`등급`, `아이템 속성`, `인챈트`, `개조`, `세공`, `에르그`, `세트아이템`, `정령`, `아이템 색상`

Only 21 unique characters across all 9 labels, so the charset is tiny. Input crops are pre-processed at threshold=50 (not 80) because orange text on black headers needs a lower threshold for clean separation.

### 4. Enchant Header (v3)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/enchant_header_model/v3/` |
| Symlink | `backend/ocr/models/custom_enchant_header.*` |
| Charset | 626 chars (`enchant_header_chars.txt`) |
| imgW | 256 |
| Font | Synthetic + real crops mixed |
| Training | 30,000 iterations, batch 32, Adam optimizer, lr=0.0003 |
| Training data | Synthetic + real crops oversampled to ~10% |
| Deploy | `bash scripts/ocr/enchant_header_model/deploy.sh v3` |
| Last updated | 2026-02-25 |

Reads enchant slot headers like `[접두] 창백한 (랭크 A)`. These appear inside the enchant section as white text on dark background, pre-processed via the "oreo flip" (white mask → invert → binary).

**Version history:**
- v1: Synthetic-only training, struggled on real crops
- v2: Improved synthetic rendering
- v3: Mixed training with real crops oversampled to 10%. Accuracy went from 46.3% to 100% on real enchant headers. Uses Adam (Adadelta failed to converge on NanumGothicBold) at a lower learning rate (0.0003) for fine-tuning.

### 5. Preheader — mabinogi_classic (v1)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/preheader_mabinogi_classic_model/v1/` |
| Symlink | `backend/ocr/models/custom_preheader_mabinogi_classic.*` |
| Charset | 1,181 chars (`unique_chars.txt`) |
| imgW | 200 (fixed via `ocr_utils.py` patch) |
| Font | `data/fonts/mabinogi_classic.ttf` |
| Training | 10,000 iterations, batch 64 |
| Training data | Synthetic (game-like rendering pipeline) |
| Deploy | `bash scripts/ocr/preheader_mabinogi_classic_model/deploy.sh v1` |
| Last updated | 2026-02-27 |

Dedicated to the pre-header region (above the first orange header band) which contains item names, enchant names, and basic attributes. Has a much larger charset (1,181 vs 554) because item names include rare characters not found in section content text.

### 6. Preheader — NanumGothicBold (v1)

| Field | Value |
|-------|-------|
| Path | `backend/ocr/preheader_nanum_gothic_model/v1/` |
| Symlink | `backend/ocr/models/custom_preheader_nanum_gothic.*` |
| Charset | 1,181 chars (`unique_chars.txt`) |
| imgW | 200 (fixed via `ocr_utils.py` patch) |
| Font | `data/fonts/NanumGothicBold.ttf` |
| Training | 10,000 iterations, batch 64 |
| Training data | Synthetic (game-like rendering pipeline) |
| Deploy | `bash scripts/ocr/preheader_nanum_gothic_model/deploy.sh v1` |
| Last updated | 2026-02-27 |

NanumGothicBold counterpart of the preheader mabinogi_classic model. Same charset, same DualReader pattern (both run, highest confidence wins).

### 7. Legacy Content (a18) — Rollback Only

| Field | Value |
|-------|-------|
| Path | `backend/ocr/general_model/a18/` |
| Symlink | None (previously `custom_mabinogi.*`, now replaced by font-specific models) |
| Charset | 554 chars (`unique_chars.txt`) |
| imgW | 200 (fixed via `ocr_utils.py` patch) |
| Font | Both fonts mixed in training data |
| Training | 20,000 iterations, batch 64 |
| Training data | Synthetic (both fonts combined) |
| Deploy | `bash scripts/ocr/general_model/deploy.sh a18` |
| Last updated | 2026-02-23 |

The original single-model approach — trained on both fonts mixed together. Superseded by the a19 font-specific dual-model approach which gives better per-line accuracy. Kept for rollback if the DualReader setup has issues.

---

## Inference Architecture

### DualReader (`backend/lib/dual_reader.py`)

Wraps two EasyOCR readers. Both run `recognize()` on the same line crop image. Per-line, the result with higher confidence wins. Transparent to the parser — it sees a single "reader" object.

**Content OCR pair:** `custom_mabinogi_classic` + `custom_nanum_gothic_bold`
**Preheader OCR pair:** `custom_preheader_mabinogi_classic` + `custom_preheader_nanum_gothic`

Falls back to the legacy single model (`custom_mabinogi`) if font-specific models aren't deployed.

### Inference Patch (`backend/lib/ocr_utils.py`)

`patch_reader_imgw()` fixes two EasyOCR issues:

1. **Double-dip resize fix:** EasyOCR inference resized images twice (cv2.LANCZOS in `get_image_list()` then PIL.BICUBIC in `AlignCollate`). Training only resizes once. The patch replaces `get_image_list()` with `_crop_boxes()` that crops without resizing. This alone gave **+37 exact matches** across all models without retraining.

2. **Fixed imgW:** Uses the yaml's fixed imgW (200) instead of EasyOCR's dynamic per-image width. Mismatched imgW causes TPS layer shape errors or garbage output.

**Must always be applied** after creating any EasyOCR reader — unpatched `recognize()` suffers double-dip degradation.

---

## Symlink Layout

```
backend/ocr/models/
├── custom_mabinogi_classic.*       → ../general_mabinogi_classic_model/a19/
├── custom_nanum_gothic_bold.*      → ../general_nanum_gothic_bold_model/a19/
├── custom_header.*                 → ../category_header_model/v1/
├── custom_enchant_header.*         → ../enchant_header_model/v3/
├── custom_preheader_mabinogi_classic.* → ../preheader_mabinogi_classic_model/v1/
├── custom_preheader_nanum_gothic.* → ../preheader_nanum_gothic_model/v1/
├── craft_mlt_25k.pth              (CRAFT — not used for detection, EasyOCR requires it)
└── modules/                       (EasyOCR internals)
```

Switch active version: `bash scripts/ocr/switch_model.sh <type> <version>`

---

## Training Pipeline

See [README.md § Training](../README.md#training-custom-ocr-model) for the full training pipeline commands and scripts reference.
