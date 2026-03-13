from uuid import UUID

from db.connector import SessionLocal
from db.models import UserActivityLog
from lib.utils.log import logger


def _sanitize_metadata(metadata):
    """Stringify UUID values in metadata dict for JSONB serialization."""
    if not metadata:
        return metadata
    return {k: str(v) if isinstance(v, UUID) else v for k, v in metadata.items()}


def log_activity(
    *,
    action: str,
    user_id=None,
    target_type: str | None = None,
    target_id=None,
    metadata: dict | None = None,
):
    """Write an activity log entry using its own DB session.

    Designed to be called from BackgroundTasks (after response is sent),
    so it must not rely on the request-scoped session.
    """
    db = SessionLocal()
    try:
        entry = UserActivityLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=_sanitize_metadata(metadata),
        )
        db.add(entry)
        db.commit()
        logger.debug("activity  action=%s  user=%s  target=%s/%s", action, user_id, target_type, target_id)
    except Exception:
        db.rollback()
        logger.exception("activity log failed  action=%s", action)
    finally:
        db.close()
