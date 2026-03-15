"""Automatic audit logging for admin/system changes.

Attach to any router with a single dependency:
    router = APIRouter(dependencies=[Depends(enable_audit)])

All ORM changes on audited models within that request are logged to system_logs
with before/after diffs, automatically.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import Depends
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from db.connector import get_db
from db.models import (
    SystemLog, AutoTagRule, Tag, TagTarget,
    Listing, ListingOption, GameItem,
    User, Role, UserRole, FeatureFlag, RoleFeatureFlag,
)

# Models to audit -> columns to exclude (system fields)
_EXCLUDE = {'id', 'created_at', 'updated_at'}

_AUDITED_MODELS = {
    AutoTagRule, Tag, TagTarget,
    Listing, ListingOption, GameItem,
    User, Role, UserRole, FeatureFlag, RoleFeatureFlag,
}


def _serialize(val):
    """Convert non-JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val


def _get_columns(cls):
    """Get auditable column names for a model class."""
    return [c.key for c in cls.__table__.columns if c.key not in _EXCLUDE]


def _snapshot(obj, columns):
    """Snapshot selected columns from an ORM object."""
    return {col: _serialize(getattr(obj, col, None)) for col in columns}


def _audit_before_flush(session, flush_context, instances):
    if not session.info.get('audit'):
        return

    source = session.info.get('audit_source', 'admin')
    user_id = session.info.get('audit_user_id')
    logs = []

    # --- Inserts ---
    for obj in list(session.new):
        cls = type(obj)
        if cls not in _AUDITED_MODELS or cls is SystemLog:
            continue
        cols = _get_columns(cls)
        logs.append(SystemLog(
            source=source, user_id=user_id,
            action=f'{source}:create',
            target_type=cls.__tablename__,
            target_id=obj.id,
            before_=None,
            after_=_snapshot(obj, cols),
        ))

    # --- Updates ---
    for obj in list(session.dirty):
        cls = type(obj)
        if cls not in _AUDITED_MODELS or cls is SystemLog:
            continue
        insp = inspect(obj)
        before, after = {}, {}
        for col in _get_columns(cls):
            hist = insp.attrs[col].history
            if hist.has_changes():
                old = hist.deleted[0] if hist.deleted else None
                new = hist.added[0] if hist.added else None
                before[col] = _serialize(old)
                after[col] = _serialize(new)
        if before:
            logs.append(SystemLog(
                source=source, user_id=user_id,
                action=f'{source}:update',
                target_type=cls.__tablename__,
                target_id=obj.id,
                before_=before,
                after_=after,
            ))

    # --- Deletes ---
    for obj in list(session.deleted):
        cls = type(obj)
        if cls not in _AUDITED_MODELS or cls is SystemLog:
            continue
        cols = _get_columns(cls)
        logs.append(SystemLog(
            source=source, user_id=user_id,
            action=f'{source}:delete',
            target_type=cls.__tablename__,
            target_id=obj.id,
            before_=_snapshot(obj, cols),
            after_=None,
        ))

    for log in logs:
        session.add(log)


# Register the event listener globally (fires only when session.info['audit'] is set)
event.listen(Session, "before_flush", _audit_before_flush)


def enable_audit(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """FastAPI dependency — marks the DB session for audit logging."""
    db.info['audit'] = True
    db.info['audit_source'] = 'admin'
    db.info['audit_user_id'] = current_user.id
