from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User, SystemLog
from auth.dependencies import require_role

router = APIRouter()

_master_required = Depends(require_role("master"))


class AdminSystemLogsParams:
    def __init__(
        self,
        source: str = Query(default=""),
        action: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        self.source = source
        self.action = action
        self.limit = limit
        self.offset = offset


@router.get("/system-logs")
def admin_list_system_logs(
    params: AdminSystemLogsParams = Depends(),
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    q = db.query(SystemLog)
    if params.source:
        q = q.filter(SystemLog.source == params.source)
    if params.action:
        q = q.filter(SystemLog.action == params.action)

    total = q.count()
    rows = q.order_by(SystemLog.created_at.desc()).offset(params.offset).limit(params.limit).all()

    return {
        "total": total,
        "limit": params.limit,
        "offset": params.offset,
        "rows": [
            {
                "id": r.id,
                "source": r.source,
                "user_id": r.user_id,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "before": r.before_,
                "after": r.after_,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/system-logs/actions")
def admin_list_system_log_actions(
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    rows = (
        db.query(SystemLog.action, func.count(SystemLog.id))
        .group_by(SystemLog.action)
        .order_by(func.count(SystemLog.id).desc())
        .all()
    )
    return [{"action": action, "count": count} for action, count in rows]
