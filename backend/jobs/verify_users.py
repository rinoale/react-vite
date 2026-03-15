"""Scheduled job: poll horn bugle API and verify pending users."""
from sqlalchemy.orm import Session

from lib.api.nexon_open_api import get_horn_bugle_history
from auth.services.verification_service import check_horn_bugle_messages, cleanup_expired, SERVERS
from lib.utils.log import logger


def verify_users_from_horn_bugle(db: Session, *, payload: dict | None = None) -> str:
    """Poll all servers and check for verification codes in horn bugle messages."""
    total_verified = 0
    errors = []

    for server in SERVERS:
        try:
            data = get_horn_bugle_history(server)
            messages = data.get('horn_bugle_world_history', [])
            count = check_horn_bugle_messages(messages=messages, server=server, db=db)
            if count:
                total_verified += count
                logger.info("verify-job  server=%s verified=%d", server, count)
        except Exception as e:
            errors.append(f"{server}: {e}")
            logger.exception("verify-job  server=%s failed", server)

    expired = cleanup_expired(db=db)

    parts = [f"Verified {total_verified} users"]
    if expired:
        parts.append(f"cleaned {expired} expired codes")
    if errors:
        parts.append(f"errors: {', '.join(errors)}")
    return '. '.join(parts)
