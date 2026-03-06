from html import escape
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import User
from crud import admin as crud_admin
from crud import user as crud_user
from auth.dependencies import require_role, require_feature

router = APIRouter(prefix="/admin", tags=["admin"])

_admin_required = Depends(require_role("admin"))
_manage_tags = Depends(require_feature("manage_tags"))
_master_required = Depends(require_role("master"))

_ALLOWED_TABS = {"enchants", "effects", "enchant_effects", "reforge"}


def _slot_label(slot: int | None) -> str:
    if slot == 0:
        return "prefix"
    if slot == 1:
        return "suffix"
    return "unknown"


def _render_table(rows: list[Any]) -> str:
    if not rows:
        return "<p>No records.</p>"

    # Handle both dict-like and object-like rows
    if hasattr(rows[0], "__dict__") and not isinstance(rows[0], dict):
        # Filter out SQLAlchemy internal state
        headers = [k for k in rows[0].__dict__.keys() if not k.startswith('_')]
    else:
        headers = list(rows[0].keys())

    th = "".join(f"<th>{escape(str(h))}</th>" for h in headers)

    body_rows = []
    for row in rows:
        td = ""
        for h in headers:
            val = row[h] if isinstance(row, dict) else getattr(row, h, None)
            if h == "slot":
                val = f"{val} ({_slot_label(val)})"
            td += f"<td>{escape('' if val is None else str(val))}</td>"
        body_rows.append(f"<tr>{td}</tr>")

    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


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
    enchant_id: int,
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


@router.get("/listings/{listing_id}/detail", response_model=schemas.ListingDetailOut)
def admin_listing_detail(
    listing_id: int,
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    result = crud_admin.get_listing_detail(db, listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result


@router.get("/listings", response_model=schemas.PaginatedListingResponse)
def admin_listings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_listings(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/game-items", response_model=schemas.PaginatedGameItemResponse)
def admin_game_items(
    q: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_game_items(db, q=q or None, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/tags")
def admin_tags(
    target_type: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_tags(db, target_type=target_type or None, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.post("/tags", response_model=schemas.TagTargetOut)
def admin_create_tag(
    data: schemas.TagCreate,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
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
    tag_target_id: int,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
):
    if not crud_admin.delete_tag(db, tag_target_id):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"deleted": True}


@router.get("/tags/unique")
def admin_unique_tags(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    rows = crud_admin.get_unique_tags(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.delete("/tags/by-tag/{tag_id}")
def admin_delete_tag_by_id(
    tag_id: int,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
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
    _: User = _admin_required,
):
    if not q.strip():
        return []
    return crud_admin.search_entities(db, target_type, q.strip(), limit=limit, like=like)


@router.post("/tags/bulk")
def admin_bulk_create_tags(
    data: schemas.BulkTagCreate,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
):
    return crud_admin.bulk_create_tags(db, data)


@router.patch("/tags/targets/{tag_target_id}")
def admin_update_tag_target_weight(
    tag_target_id: int,
    data: schemas.WeightUpdate,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
):
    if not crud_admin.update_tag_target_weight(db, tag_target_id, data.weight):
        raise HTTPException(status_code=404, detail="Tag target not found")
    return {"ok": True}


@router.patch("/tags/targets/bulk")
def admin_bulk_update_tag_target_weights(
    data: schemas.BulkWeightUpdate,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
):
    return crud_admin.bulk_update_tag_target_weights(db, data.ids, data.weight)


@router.get("/tags/{tag_id}", response_model=schemas.TagDetail)
def admin_tag_detail(
    tag_id: int,
    db: Session = Depends(get_db),
    _: User = _admin_required,
):
    result = crud_admin.get_tag_detail(db, tag_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return result


@router.patch("/tags/{tag_id}")
def admin_update_tag_weight(
    tag_id: int,
    data: schemas.WeightUpdate,
    db: Session = Depends(get_db),
    _: User = _manage_tags,
):
    if not crud_admin.update_tag_weight(db, tag_id, data.weight):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}


@router.get("/validate", response_class=HTMLResponse)
def admin_validate_page(
    tab: str = Query(default="enchants"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _admin_required,
) -> HTMLResponse:
    tab = tab if tab in _ALLOWED_TABS else "enchants"
    summary = crud_admin.get_summary(db)

    if tab == "enchants":
        rows = crud_admin.get_enchants(db, limit, offset)
    elif tab == "effects":
        rows = crud_admin.get_effects(db, limit, offset)
    elif tab == "enchant_effects":
        rows = crud_admin.get_enchant_effects(db, limit, offset)
    else:
        rows = crud_admin.get_reforge_options(db, limit, offset)

    next_offset = offset + limit
    prev_offset = max(0, offset - limit)

    html = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Admin DB Validation</title>
</head>
<body style=\"font-family: Arial, sans-serif; margin: 24px;\">
  <h1>Admin DB Validation</h1>
  <p>
    enchants={summary['enchants']} |
    effects={summary['effects']} |
    enchant_effects={summary['enchant_effects']} |
    reforge={summary['reforge_options']} |
    listings={summary['listings']} |
    game_items={summary['game_items']}
  </p>
  <p>
    <a href=\"/admin/validate?tab=enchants&limit={limit}&offset=0\">enchants</a> |
    <a href=\"/admin/validate?tab=effects&limit={limit}&offset=0\">effects</a> |
    <a href=\"/admin/validate?tab=enchant_effects&limit={limit}&offset=0\">enchant_effects</a> |
    <a href=\"/admin/validate?tab=reforge&limit={limit}&offset=0\">reforge</a>
  </p>
  <p>Current tab: <strong>{escape(tab)}</strong> / limit={limit} / offset={offset}</p>
  <p>
    <a href=\"/admin/validate?tab={escape(tab)}&limit={limit}&offset={prev_offset}\">prev</a> |
    <a href=\"/admin/validate?tab={escape(tab)}&limit={limit}&offset={next_offset}\">next</a>
  </p>
  {_render_table(rows)}
  <hr/>
  <p>JSON endpoints: /admin/summary, /admin/enchant-entries, /admin/effects, /admin/links, /admin/reforge-options, /admin/listings, /admin/game-items</p>
</body>
</html>
"""
    return HTMLResponse(content=html)


# --- User, role & feature management (master only) ---

@router.get("/users")
def admin_list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    from db.models import User as UserModel
    users = db.query(UserModel).order_by(UserModel.id).offset(offset).limit(limit).all()
    return {
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "id": u.id,
                "email": u.email,
                "discord_username": u.discord_username,
                "server": u.server,
                "game_id": u.game_id,
                "status": u.status,
                "verified": u.verified,
                "created_at": u.created_at,
                "roles": crud_user.get_user_roles(db, u.id),
                "features": crud_user.get_user_features(db, u.id),
            }
            for u in users
        ],
    }


@router.get("/roles")
def admin_list_roles(db: Session = Depends(get_db), _: User = _master_required):
    from db.models import Role, RoleFeatureFlag, FeatureFlag
    roles = db.query(Role).order_by(Role.id).all()
    result = []
    for role in roles:
        flags = (
            db.query(FeatureFlag.name)
            .join(RoleFeatureFlag)
            .filter(RoleFeatureFlag.role_id == role.id)
            .all()
        )
        result.append({"id": role.id, "name": role.name, "features": [f[0] for f in flags]})
    return result


@router.get("/feature-flags")
def admin_list_feature_flags(db: Session = Depends(get_db), _: User = _master_required):
    from db.models import FeatureFlag
    flags = db.query(FeatureFlag).order_by(FeatureFlag.id).all()
    return [{"id": f.id, "name": f.name} for f in flags]


@router.post("/users/{user_id}/roles/{role_name}")
def admin_assign_role(
    user_id: int, role_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.assign_role(db, user_id, role_name):
        raise HTTPException(status_code=404, detail="User or role not found")
    return {"ok": True}


@router.delete("/users/{user_id}/roles/{role_name}")
def admin_remove_role(
    user_id: int, role_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.remove_role(db, user_id, role_name):
        raise HTTPException(status_code=404, detail="User role not found")
    return {"ok": True}


@router.post("/roles/{role_name}/features/{flag_name}")
def admin_assign_feature(
    role_name: str, flag_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.assign_feature_to_role(db, role_name, flag_name):
        raise HTTPException(status_code=404, detail="Role or feature flag not found")
    return {"ok": True}


@router.delete("/roles/{role_name}/features/{flag_name}")
def admin_remove_feature(
    role_name: str, flag_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.remove_feature_from_role(db, role_name, flag_name):
        raise HTTPException(status_code=404, detail="Role feature flag not found")
    return {"ok": True}
