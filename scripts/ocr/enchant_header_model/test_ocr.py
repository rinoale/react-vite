#!/usr/bin/env python3
"""OCR oreo_flipped enchant header crops using the enchant header model.

Takes image files (already preprocessed black-on-white crops) and runs
the enchant header OCR model on each.  When a .txt GT file exists next
to the image (same basename), compares OCR output against it and prints
accuracy stats.

Usage (from project root):
    python3 scripts/ocr/enchant_header_model/test_ocr.py tmp/enchant_header_samples2/*.png
    python3 scripts/ocr/enchant_header_model/test_ocr.py tmp/enchant_header_samples2/293_enchant_hdr.png
"""

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))

from lib.tooltip_segmenter import init_enchant_header_reader

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend', 'ocr', 'models')


def _char_accuracy(ocr_text, gt_text):
    """Levenshtein-based character accuracy: 1 - (edit_dist / max_len)."""
    m, n = len(ocr_text), len(gt_text)
    if m == 0 and n == 0:
        return 1.0
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            cur = dp[j]
            if ocr_text[i - 1] == gt_text[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return 1.0 - dp[n] / max(m, n)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ocr/enchant_header_model/test_ocr.py <image>...")
        sys.exit(1)

    # Expand globs
    paths = []
    for arg in sys.argv[1:]:
        expanded = sorted(glob.glob(arg))
        paths.extend(expanded if expanded else [arg])

    print("Loading enchant header reader...")
    reader = init_enchant_header_reader(models_dir=os.path.abspath(MODELS_DIR))
    print(f"Processing {len(paths)} image(s)...\n")

    gt_total = 0
    gt_exact = 0
    gt_char_acc_sum = 0.0
    mismatches = []

    for path in paths:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"  {os.path.basename(path):40s}  FAILED to load")
            continue

        h, w = img.shape
        result = reader.recognize(img, horizontal_list=[[0, w, 0, h]], free_list=[])

        text = result[0][1] if result else ''
        conf = float(result[0][2]) if result else 0.0

        # Check for GT file
        gt_path = os.path.splitext(path)[0] + '.txt'
        gt_text = None
        if os.path.isfile(gt_path):
            with open(gt_path, 'r', encoding='utf-8') as f:
                gt_text = f.read().strip()

        if gt_text is not None:
            gt_total += 1
            exact = (text == gt_text)
            char_acc = _char_accuracy(text, gt_text)
            gt_char_acc_sum += char_acc
            if exact:
                gt_exact += 1
                print(f"  ✓ {os.path.basename(path):40s}  conf={conf:.3f}  → {text}")
            else:
                mismatches.append((os.path.basename(path), gt_text, text, conf, char_acc))
                print(f"  ✗ {os.path.basename(path):40s}  conf={conf:.3f}  → {text}")
                print(f"    {'':40s}  GT: {gt_text}  (char_acc={char_acc:.1%})")
        else:
            if result:
                print(f"  {os.path.basename(path):40s}  conf={conf:.3f}  → {text}")
            else:
                print(f"  {os.path.basename(path):40s}  (no result)")

    # Summary
    if gt_total > 0:
        avg_char_acc = gt_char_acc_sum / gt_total
        print(f"\n{'=' * 70}")
        print(f"  GT comparison: {gt_exact}/{gt_total} exact ({100*gt_exact/gt_total:.1f}%)"
              f"  char_acc={avg_char_acc:.1%}")
        if mismatches:
            print(f"\n  Mismatches ({len(mismatches)}):")
            for fname, gt, ocr, conf, ca in mismatches:
                print(f"    {fname}")
                print(f"      GT:  {gt}")
                print(f"      OCR: {ocr}  (conf={conf:.3f}, char_acc={ca:.1%})")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
