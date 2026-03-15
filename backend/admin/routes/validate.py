from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from admin.services.summary_service import get_summary
from admin.services.enchant_service import get_enchants, get_effects, get_enchant_effects
from admin.services.reforge_service import get_reforge_options

router = APIRouter()

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


@router.get("/validate", response_class=HTMLResponse)
def admin_validate_page(
    tab: str = Query(default="enchants"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    tab = tab if tab in _ALLOWED_TABS else "enchants"
    summary = get_summary(db=db)

    if tab == "enchants":
        rows = get_enchants(db=db, limit=limit, offset=offset)
    elif tab == "effects":
        rows = get_effects(db=db, limit=limit, offset=offset)
    elif tab == "enchant_effects":
        rows = get_enchant_effects(db=db, limit=limit, offset=offset)
    else:
        rows = get_reforge_options(db=db, limit=limit, offset=offset)

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
  <p>JSON endpoints: /admin/summary, /admin/enchants, /admin/effects, /admin/links, /admin/reforge-options, /admin/listings, /admin/game-items</p>
</body>
</html>
"""
    return HTMLResponse(content=html)
