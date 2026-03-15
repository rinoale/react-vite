"""In-game verification via horn bugle (all-chat) OTP."""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import User, VerificationCode
from lib.utils.log import logger

CODE_PREFIX = '마트레'
CODE_DIGITS = 6
CODE_TTL_MINUTES = 30
SERVERS = ['류트', '만돌린', '하프', '울프']


def _generate_code() -> str:
    digits = ''.join(str(random.randint(0, 9)) for _ in range(CODE_DIGITS))
    return f'{CODE_PREFIX}-{digits}'


def request_verification(*, user_id, db: Session) -> dict:
    """Generate a verification code for the user. Returns the code to display."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {'error': 'User not found'}
    if not user.server or not user.game_id:
        return {'error': 'Server and game ID must be set before verification'}
    if user.verified:
        return {'error': 'Already verified'}

    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)

    existing = db.query(VerificationCode).filter(VerificationCode.user_id == user_id).first()
    if existing:
        existing.code = code
        existing.expires_at = expires_at
    else:
        db.add(VerificationCode(user_id=user_id, code=code, expires_at=expires_at))
    db.commit()

    return {'code': code, 'expires_at': expires_at.isoformat()}


def check_horn_bugle_messages(*, messages: list[dict], server: str, db: Session) -> int:
    """Check horn bugle messages against pending verification codes.

    Args:
        messages: list of {'character_name': str, 'message': str, ...}
        server: server name these messages came from
        db: database session

    Returns:
        Number of users verified.
    """
    now = datetime.now(timezone.utc)
    pending = (
        db.query(VerificationCode)
        .join(User)
        .filter(
            User.server == server,
            User.verified.is_(False),
            VerificationCode.expires_at > now,
        )
        .all()
    )
    if not pending:
        return 0

    # Build lookup: game_id -> verification record
    code_map = {}
    for vc in pending:
        user = vc.user
        if user.game_id:
            code_map[user.game_id] = vc

    verified_count = 0
    for msg in messages:
        name = msg.get('character_name', '')
        text = msg.get('message', '')
        if name not in code_map:
            continue
        vc = code_map[name]
        if vc.code in text:
            vc.user.verified = True
            db.delete(vc)
            verified_count += 1
            logger.info("verification  user=%s game_id=%s server=%s verified", vc.user_id, name, server)
            del code_map[name]

    if verified_count:
        db.commit()
    return verified_count


def cleanup_expired(*, db: Session) -> int:
    """Delete expired verification codes."""
    now = datetime.now(timezone.utc)
    count = db.query(VerificationCode).filter(VerificationCode.expires_at <= now).delete()
    db.commit()
    return count
