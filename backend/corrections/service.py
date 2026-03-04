import os
import re

from sqlalchemy.orm import Session

from db.models import OcrCorrection

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')

_SESSION_ID_RE = re.compile(r'[a-f0-9\-]{36}')
_FILENAME_RE = re.compile(r'[a-z_]*[0-9]{3}\.png')


def list_corrections(db, status="pending", limit=100, offset=0):
    """List corrections filtered by status."""
    return (
        db.query(OcrCorrection)
        .filter(OcrCorrection.status == status)
        .order_by(OcrCorrection.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def approve_correction(db, correction_id):
    """Set a correction's status to 'approved'.

    Returns (row, error_msg). error_msg is None on success.
    """
    row = db.query(OcrCorrection).filter(OcrCorrection.id == correction_id).first()
    if not row:
        return None, "Correction not found"
    if row.status != 'pending':
        return None, f"Cannot approve from status '{row.status}'"
    row.status = 'approved'
    db.commit()
    return row, None


def edit_correction(db, correction_id, corrected_text):
    """Edit the corrected_text of a pending correction.

    Returns (row, error_msg). error_msg is None on success.
    """
    row = db.query(OcrCorrection).filter(OcrCorrection.id == correction_id).first()
    if not row:
        return None, "Correction not found"
    if row.status != 'pending':
        return None, f"Cannot edit correction with status '{row.status}'"
    row.corrected_text = corrected_text
    db.commit()
    return row, None


def truncate_corrections(db):
    """Delete all corrections. Returns the count deleted."""
    count = db.query(OcrCorrection).count()
    db.query(OcrCorrection).delete()
    db.commit()
    return count


def resolve_crop_path(session_id, filename):
    """Validate inputs and resolve crop image path.

    Returns (path, error_msg). error_msg is None on success.
    """
    if not _FILENAME_RE.fullmatch(filename):
        return None, "Invalid filename"
    if not _SESSION_ID_RE.fullmatch(session_id):
        return None, "Invalid session_id"

    for base in (_CORRECTIONS_DIR, _CROPS_DIR):
        path = os.path.join(base, session_id, filename)
        if os.path.isfile(path):
            return path, None

    return None, "Crop not found"
