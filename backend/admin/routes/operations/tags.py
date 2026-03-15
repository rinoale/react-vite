from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from admin.schemas.tags import (
    TagCreate, TagTargetOut, BulkTagCreate,
    WeightUpdate, BulkWeightUpdate, TagDetail,
)
from admin.services.tag_service import (
    get_tags, create_tag, delete_tag, search_entities, bulk_create_tags,
    get_unique_tags, delete_tag_by_id, get_tag_detail,
    update_tag_weight, update_tag_target_weight, bulk_update_tag_target_weights,
)

router = APIRouter()


class AdminTagsParams:
    def __init__(
        self,
        target_type: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        self.target_type = target_type
        self.limit = limit
        self.offset = offset


@router.get("/tags")
def admin_tags(params: AdminTagsParams = Depends(), db: Session = Depends(get_db)):
    rows = get_tags(db=db, target_type=params.target_type or None, limit=params.limit, offset=params.offset)
    return {"limit": params.limit, "offset": params.offset, "rows": rows}


@router.post("/tags", response_model=TagTargetOut)
def admin_create_tag(
    data: TagCreate,
    db: Session = Depends(get_db),
):
    tt = create_tag(db=db, data=data)
    if tt is None:
        raise HTTPException(status_code=409, detail="Tag already exists for this target")
    rows = get_tags(db=db, limit=1, offset=0)
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
    if not delete_tag(db=db, tag_target_id=tag_target_id):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"deleted": True}


class AdminUniqueTagsParams:
    def __init__(
        self,
        q: str = Query(default=""),
        sort: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        self.q = q
        self.sort = sort
        self.limit = limit
        self.offset = offset


@router.get("/tags/unique")
def admin_unique_tags(params: AdminUniqueTagsParams = Depends(), db: Session = Depends(get_db)):
    rows = get_unique_tags(db=db, limit=params.limit, offset=params.offset, q=params.q or None, sort=params.sort or None)
    return {"limit": params.limit, "offset": params.offset, "rows": rows}


@router.delete("/tags/by-tag/{tag_id}")
def admin_delete_tag_by_id(
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    if not delete_tag_by_id(db=db, tag_id=tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"deleted": True}


class AdminSearchTagEntitiesParams:
    def __init__(
        self,
        target_type: str = Query(...),
        q: str = Query(default=""),
        like: bool = Query(default=True),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        self.target_type = target_type
        self.q = q
        self.like = like
        self.limit = limit


@router.get("/tags/search-entities")
def admin_search_tag_entities(params: AdminSearchTagEntitiesParams = Depends(), db: Session = Depends(get_db)):
    if not params.q.strip():
        return []
    return search_entities(db=db, target_type=params.target_type, q=params.q.strip(), limit=params.limit, like=params.like)


@router.post("/tags/bulk")
def admin_bulk_create_tags(
    data: BulkTagCreate,
    db: Session = Depends(get_db),
):
    return bulk_create_tags(db=db, data=data)


@router.patch("/tags/targets/{tag_target_id}")
def admin_update_tag_target_weight(
    tag_target_id: UUID,
    data: WeightUpdate,
    db: Session = Depends(get_db),
):
    if not update_tag_target_weight(db=db, tag_target_id=tag_target_id, weight=data.weight):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"ok": True}


@router.patch("/tags/targets/bulk")
def admin_bulk_update_tag_target_weights(
    data: BulkWeightUpdate,
    db: Session = Depends(get_db),
):
    return bulk_update_tag_target_weights(db=db, ids=data.ids, weight=data.weight)


@router.get("/tags/{tag_id}", response_model=TagDetail)
def admin_tag_detail(
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    result = get_tag_detail(db=db, tag_id=tag_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return result


@router.patch("/tags/{tag_id}")
def admin_update_tag_weight(
    tag_id: UUID,
    data: WeightUpdate,
    db: Session = Depends(get_db),
):
    if not update_tag_weight(db=db, tag_id=tag_id, weight=data.weight):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}
