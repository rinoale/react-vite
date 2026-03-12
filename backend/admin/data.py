from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import User
from crud import admin as crud_admin
from auth.dependencies import require_role

router = APIRouter()

_admin_required = Depends(require_role("admin"))


@router.get("/health")
def admin_health(_: User = _admin_required) -> dict[str, bool]:
    return {"ok": True}


@router.get("/summary", response_model=schemas.SummarySchema)
def admin_summary(db: Session = Depends(get_db), _: User = _admin_required):
    return crud_admin.get_summary(db)


@router.get("/enchant-entries", response_model=schemas.PaginatedEnchantResponse)
def admin_enchant_entries(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_enchants(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/enchant-entries/{enchant_id}/effects", response_model=List[schemas.EnchantEffect])
def admin_enchant_effects_by_id(
    enchant_id: UUID,
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    return crud_admin.get_enchant_effects_by_id(db, enchant_id)


@router.get("/effects", response_model=schemas.PaginatedEffectResponse)
def admin_effects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_effects(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/links", response_model=schemas.PaginatedEnchantEffectResponse)
def admin_links(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_enchant_effects(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/reforge-options", response_model=schemas.PaginatedReforgeResponse)
def admin_reforge_options(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_reforge_options(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/echostone-options", response_model=schemas.PaginatedEchostoneResponse)
def admin_echostone_options(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_echostone_options(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/murias-relic-options", response_model=schemas.PaginatedMuriasRelicResponse)
def admin_murias_relic_options(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_murias_relic_options(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}
