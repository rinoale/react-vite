from html import escape
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from crud import admin as crud_admin

router = APIRouter(prefix="/admin", tags=["admin"])

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
def admin_health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/summary", response_model=schemas.SummarySchema)
def admin_summary(db: Session = Depends(get_db)):
    return crud_admin.get_summary(db)


@router.get("/enchant-entries", response_model=schemas.PaginatedEnchantResponse)
def admin_enchant_entries(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_enchants(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/enchant-entries/{enchant_id}/effects", response_model=List[schemas.EnchantEffect])
def admin_enchant_effects_by_id(
    enchant_id: int,
    db: Session = Depends(get_db),
):
    return crud_admin.get_enchant_effects_by_id(db, enchant_id)


@router.get("/effects", response_model=schemas.PaginatedEffectResponse)
def admin_effects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_effects(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/links", response_model=schemas.PaginatedEnchantEffectResponse)
def admin_links(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_enchant_effects(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/reforge-options", response_model=schemas.PaginatedReforgeResponse)
def admin_reforge_options(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_reforge_options(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/items/{item_id}/detail", response_model=schemas.ItemDetailOut)
def admin_item_detail(
    item_id: int,
    db: Session = Depends(get_db),
):
    result = crud_admin.get_item_detail(db, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@router.get("/items", response_model=schemas.PaginatedItemResponse)
def admin_items(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_items(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/validate", response_class=HTMLResponse)
def admin_validate_page(
    tab: str = Query(default="enchants"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
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
    items={summary['items']}
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
  <p>JSON endpoints: /admin/summary, /admin/enchant-entries, /admin/effects, /admin/links, /admin/reforge-options</p>
</body>
</html>
"""
    return HTMLResponse(content=html)
