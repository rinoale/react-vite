import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import OcrCorrection

router = APIRouter(prefix="/admin/corrections", tags=["corrections"])

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')


class CorrectionEdit(BaseModel):
    corrected_text: str


@router.get("/list", response_model=list[schemas.CorrectionOut])
def list_corrections(
    status: str = Query("pending"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List corrections filtered by status."""
    return (
        db.query(OcrCorrection)
        .filter(OcrCorrection.status == status)
        .order_by(OcrCorrection.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/approve/{correction_id}")
def approve_correction(correction_id: int, db: Session = Depends(get_db)):
    """Set a correction's status to 'approved'."""
    row = db.query(OcrCorrection).filter(OcrCorrection.id == correction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Correction not found")
    if row.status != 'pending':
        raise HTTPException(status_code=400, detail=f"Cannot approve from status '{row.status}'")
    row.status = 'approved'
    db.commit()
    return {"id": row.id, "status": row.status}


@router.patch("/{correction_id}")
def edit_correction(correction_id: int, body: CorrectionEdit, db: Session = Depends(get_db)):
    """Edit the corrected_text of a pending correction."""
    row = db.query(OcrCorrection).filter(OcrCorrection.id == correction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Correction not found")
    if row.status != 'pending':
        raise HTTPException(status_code=400, detail=f"Cannot edit correction with status '{row.status}'")
    row.corrected_text = body.corrected_text
    db.commit()
    return {"id": row.id, "corrected_text": row.corrected_text}


@router.get("/crop/{session_id}/{filename}")
def get_correction_crop(session_id: str, filename: str):
    """Serve a crop image for correction review."""
    if not re.fullmatch(r'[0-9]{3}\.png', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not re.fullmatch(r'[a-f0-9\-]{36}', session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id")

    for base in (_CORRECTIONS_DIR, _CROPS_DIR):
        path = os.path.join(base, session_id, filename)
        if os.path.isfile(path):
            return FileResponse(path, media_type="image/png")

    raise HTTPException(status_code=404, detail="Crop not found")
