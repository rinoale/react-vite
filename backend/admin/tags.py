from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from crud import admin as crud_admin

router = APIRouter()


@router.get("/tags")
def admin_tags(
    target_type: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_tags(db, target_type=target_type or None, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.post("/tags", response_model=schemas.TagTargetOut)
def admin_create_tag(
    data: schemas.TagCreate,
    db: Session = Depends(get_db),
):
    tt = crud_admin.create_tag(db, data)
    if tt is None:
        raise HTTPException(status_code=409, detail="Tag already exists for this target")
    # Re-fetch with display name
    rows = crud_admin.get_tags(db, limit=1, offset=0)
    return rows[0] if rows and rows[0]['id'] == tt.id else {
        "id": tt.id,
        "tag_id": tt.tag_id,
        "target_type": tt.target_type,
        "target_id": tt.target_id,
        "name": data.name,
        "weight": data.weight,
    }


@router.delete("/tags/{tag_target_id}")
def admin_delete_tag(
    tag_target_id: UUID,
    db: Session = Depends(get_db),
):
    if not crud_admin.delete_tag(db, tag_target_id):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"deleted": True}


@router.get("/tags/unique")
def admin_unique_tags(
    q: str = Query(default=""),
    sort: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_unique_tags(db, limit=limit, offset=offset, q=q or None, sort=sort or None)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.delete("/tags/by-tag/{tag_id}")
def admin_delete_tag_by_id(
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    if not crud_admin.delete_tag_by_id(db, tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"deleted": True}


@router.get("/tags/search-entities")
def admin_search_tag_entities(
    target_type: str = Query(...),
    q: str = Query(default=""),
    like: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not q.strip():
        return []
    return crud_admin.search_entities(db, target_type, q.strip(), limit=limit, like=like)


@router.post("/tags/bulk")
def admin_bulk_create_tags(
    data: schemas.BulkTagCreate,
    db: Session = Depends(get_db),
):
    return crud_admin.bulk_create_tags(db, data)


@router.patch("/tags/targets/{tag_target_id}")
def admin_update_tag_target_weight(
    tag_target_id: UUID,
    data: schemas.WeightUpdate,
    db: Session = Depends(get_db),
):
    if not crud_admin.update_tag_target_weight(db, tag_target_id, data.weight):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"ok": True}


@router.patch("/tags/targets/bulk")
def admin_bulk_update_tag_target_weights(
    data: schemas.BulkWeightUpdate,
    db: Session = Depends(get_db),
):
    return crud_admin.bulk_update_tag_target_weights(db, data.ids, data.weight)


@router.get("/tags/{tag_id}", response_model=schemas.TagDetail)
def admin_tag_detail(
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    result = crud_admin.get_tag_detail(db, tag_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return result


@router.patch("/tags/{tag_id}")
def admin_update_tag_weight(
    tag_id: UUID,
    data: schemas.WeightUpdate,
    db: Session = Depends(get_db),
):
    if not crud_admin.update_tag_weight(db, tag_id, data.weight):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}
