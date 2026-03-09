from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import User
from corrections.service import (
    list_corrections as svc_list_corrections,
    approve_correction as svc_approve_correction,
    edit_correction as svc_edit_correction,
    truncate_corrections as svc_truncate_corrections,
    resolve_crop_path,
)
from auth.dependencies import require_feature

router = APIRouter(prefix="/admin/corrections", tags=["corrections"])

_manage_corrections = Depends(require_feature("manage_corrections"))


class CorrectionEdit(BaseModel):
    corrected_text: str


@router.get("/list", response_model=list[schemas.CorrectionOut])
def list_corrections(
    status: str = Query("pending"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = _manage_corrections,
):
    return svc_list_corrections(db, status=status, limit=limit, offset=offset)


@router.post("/approve/{correction_id}")
def approve_correction(correction_id: int, db: Session = Depends(get_db), _: User = _manage_corrections):
    row, error = svc_approve_correction(db, correction_id)
    if error:
        status_code = 404 if "not found" in error else 400
        raise HTTPException(status_code=status_code, detail=error)
    return {"id": row.id, "status": row.status}


@router.patch("/{correction_id}")
def edit_correction(correction_id: int, body: CorrectionEdit, db: Session = Depends(get_db), _: User = _manage_corrections):
    row, error = svc_edit_correction(db, correction_id, body.corrected_text)
    if error:
        status_code = 404 if "not found" in error else 400
        raise HTTPException(status_code=status_code, detail=error)
    return {"id": row.id, "corrected_text": row.corrected_text}


@router.delete("/truncate")
def truncate_corrections(db: Session = Depends(get_db), _: User = _manage_corrections):
    count = svc_truncate_corrections(db)
    return {"deleted": count}


@router.get("/crop/{session_id}/{filename}")
def get_correction_crop(session_id: str, filename: str):
    path, error = resolve_crop_path(session_id, filename)
    if error:
        status_code = 400 if error != "Crop not found" else 404
        raise HTTPException(status_code=status_code, detail=error)
    return FileResponse(path, media_type="image/png")
