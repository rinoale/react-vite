import json
import os
import shutil

from db.models import OcrCorrection
from lib.utils.log import logger

# --- Correction capture constants ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')
_MODELS_DIR = os.path.join(_BASE_DIR, 'ocr', 'models')


def _load_charsets():
    """Load per-model charsets for mismatch detection."""
    charsets = {}
    # Content models
    for yaml_prefix in ('custom_mabinogi_classic', 'custom_nanum_gothic_bold'):
        yaml_path = os.path.join(_MODELS_DIR, f'{yaml_prefix}.yaml')
        if not os.path.exists(yaml_path):
            continue
        real_path = os.path.realpath(yaml_path)
        version_dir = os.path.dirname(real_path)
        chars_file = os.path.join(version_dir, 'unique_chars.txt')
        if os.path.exists(chars_file):
            with open(chars_file, 'r', encoding='utf-8') as f:
                charsets[yaml_prefix] = set(f.read().strip())
    # Enchant header model
    enchant_hdr_dir = os.path.join(_MODELS_DIR, 'custom_enchant_header.yaml')
    if os.path.exists(enchant_hdr_dir):
        real_path = os.path.realpath(enchant_hdr_dir)
        version_dir = os.path.dirname(real_path)
        for fname in ('enchant_header_chars.txt', 'unique_chars.txt'):
            chars_file = os.path.join(version_dir, fname)
            if os.path.exists(chars_file):
                with open(chars_file, 'r', encoding='utf-8') as f:
                    charsets['enchant_header'] = set(f.read().strip())
                break
    return charsets


_CHARSETS = _load_charsets()


def capture_corrections(*, session_id, lines, db):
    """Diff submitted lines against stored OCR results and save corrections.

    Returns the number of corrections saved.
    """
    if not session_id or not lines:
        return 0

    session_dir = os.path.join(_CROPS_DIR, session_id)
    results_path = os.path.join(session_dir, 'ocr_results.json')

    if not os.path.isfile(results_path):
        return 0

    with open(results_path, 'r', encoding='utf-8') as f:
        originals = json.load(f)

    # Build lookup: (section, line_index) → original line data
    orig_by_key = {(o['section'], o['line_index']): o for o in originals}

    dest_dir = os.path.join(_CORRECTIONS_DIR, session_id)
    corrections_saved = 0

    for line in lines:
        orig = orig_by_key.get((line.section, line.line_index))
        if orig is None:
            continue

        submitted = line.text.strip()
        original = orig['text'].strip()

        if submitted == original:
            continue  # No change

        # Check charset mismatch against the model that produced this line
        charset_mismatch = None
        if _CHARSETS:
            ocr_model = orig.get('ocr_model', '')
            # Pick the right charset for this line's model
            if ocr_model == 'enchant_header':
                model_charset = _CHARSETS.get('enchant_header')
            else:
                # Content models — check union of both
                model_charset = _CHARSETS.get('custom_mabinogi_classic', set()) | _CHARSETS.get('custom_nanum_gothic_bold', set())
            if model_charset:
                bad = set(line.text) - model_charset - {' '}
                if bad:
                    charset_mismatch = ''.join(sorted(bad))

        # Copy crop image
        crop_name = f"{line.line_index:03d}.png"
        src_path = os.path.join(session_dir, line.section, crop_name)
        if not os.path.isfile(src_path):
            continue

        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src_path, os.path.join(dest_dir, f"{line.section}_{crop_name}"))

        db.add(OcrCorrection(
            session_id=session_id,
            line_index=line.line_index,
            original_text=orig.get('raw_text', orig['text']),
            corrected_text=submitted,
            confidence=orig.get('confidence'),
            section=line.section,
            ocr_model=orig.get('ocr_model', ''),
            fm_applied=orig.get('fm_applied', False),
            status='pending',
            charset_mismatch=charset_mismatch,
            image_filename=f"{line.section}_{crop_name}",
            is_stitched=orig.get('_is_stitched', False),
        ))
        corrections_saved += 1

    if corrections_saved:
        try:
            db.commit()
            logger.info("register-listing  saved %d correction(s)", corrections_saved)
        except Exception:
            db.rollback()
            logger.exception("register-listing  DB commit failed for %d correction(s)", corrections_saved)
            corrections_saved = 0

    return corrections_saved
