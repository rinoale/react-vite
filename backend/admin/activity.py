from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User, UserActivityLog
from auth.dependencies import require_role

router = APIRouter()

_master_required = Depends(require_role("master"))


@router.get("/activity-logs")
def admin_list_activity_logs(
    action: str = Query(default=""),
    user_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    q = db.query(UserActivityLog)
    if action:
        q = q.filter(UserActivityLog.action == action)
    if user_id is not None:
        q = q.filter(UserActivityLog.user_id == user_id)

    total = q.count()
    rows = q.order_by(UserActivityLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "metadata": r.metadata_,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/activity-logs/actions")
def admin_list_activity_actions(
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    """Return distinct action names with counts for filter dropdown."""
    rows = (
        db.query(UserActivityLog.action, func.count(UserActivityLog.id))
        .group_by(UserActivityLog.action)
        .order_by(func.count(UserActivityLog.id).desc())
        .all()
    )
    return [{"action": action, "count": count} for action, count in rows]
