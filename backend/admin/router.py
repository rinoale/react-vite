from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.connector import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

_ALLOWED_TABS = {"entries", "effects", "links", "reforge"}


def _slot_label(slot: int | None) -> str:
    if slot == 0:
        return "prefix"
    if slot == 1:
        return "suffix"
    return "unknown"


def _fetch_summary(db: Session) -> dict[str, int]:
    return {
        "enchant_entries": int(db.execute(text("SELECT COUNT(*) FROM enchant_entries")).scalar_one()),
        "enchant_effects": int(db.execute(text("SELECT COUNT(*) FROM enchant_effects")).scalar_one()),
        "enchant_links": int(
            db.execute(text("SELECT COUNT(*) FROM enchant_entry_effect_links")).scalar_one()
        ),
        "reforge_options": int(db.execute(text("SELECT COUNT(*) FROM reforge_options")).scalar_one()),
    }


def _fetch_entries(db: Session, limit: int, offset: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                e.id,
                e.slot,
                e.name,
                e.rank,
                e.header_text,
                COUNT(l.id) AS effect_count
            FROM enchant_entries e
            LEFT JOIN enchant_entry_effect_links l ON l.enchant_entry_id = e.id
            GROUP BY e.id
            ORDER BY e.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]


def _fetch_effects(db: Session, limit: int, offset: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id, normalized_text
            FROM enchant_effects
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]


def _fetch_links(db: Session, limit: int, offset: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                l.id,
                l.enchant_entry_id,
                l.enchant_effect_id,
                l.effect_order,
                l.condition_text,
                l.effect_value,
                l.effect_direction,
                l.raw_text,
                e.name AS enchant_name,
                ef.normalized_text AS effect_text
            FROM enchant_entry_effect_links l
            JOIN enchant_entries e ON e.id = l.enchant_entry_id
            JOIN enchant_effects ef ON ef.id = l.enchant_effect_id
            ORDER BY l.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]


def _fetch_reforge(db: Session, limit: int, offset: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id, option_name
            FROM reforge_options
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No records.</p>"

    headers = list(rows[0].keys())
    th = "".join(f"<th>{escape(str(h))}</th>" for h in headers)

    body_rows = []
    for row in rows:
        td = ""
        for h in headers:
            val = row.get(h)
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


@router.get("/summary")
def admin_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    return _fetch_summary(db)


@router.get("/enchant-entries")
def admin_enchant_entries(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _fetch_entries(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/effects")
def admin_effects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _fetch_effects(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/links")
def admin_links(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _fetch_links(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/reforge-options")
def admin_reforge_options(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _fetch_reforge(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/validate", response_class=HTMLResponse)
def admin_validate_page(
    tab: str = Query(default="entries"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    tab = tab if tab in _ALLOWED_TABS else "entries"
    summary = _fetch_summary(db)

    if tab == "entries":
        rows = _fetch_entries(db, limit, offset)
    elif tab == "effects":
        rows = _fetch_effects(db, limit, offset)
    elif tab == "links":
        rows = _fetch_links(db, limit, offset)
    else:
        rows = _fetch_reforge(db, limit, offset)

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
    entries={summary['enchant_entries']} |
    effects={summary['enchant_effects']} |
    links={summary['enchant_links']} |
    reforge={summary['reforge_options']}
  </p>
  <p>
    <a href=\"/admin/validate?tab=entries&limit={limit}&offset=0\">entries</a> |
    <a href=\"/admin/validate?tab=effects&limit={limit}&offset=0\">effects</a> |
    <a href=\"/admin/validate?tab=links&limit={limit}&offset=0\">links</a> |
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
