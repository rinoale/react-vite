from fastapi import Cookie, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User
from auth.service import decode_token
from crud.user import get_user_by_id, get_user_roles, get_user_features

_bearer = HTTPBearer(auto_error=False)


def _extract_user(
    token: str | None,
    db: Session,
    *,
    required: bool,
) -> User | None:
    if not token:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return None

    user = get_user_by_id(db, int(payload["sub"]))
    if not user or user.status != 0:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
        return None

    return user


def _resolve_token(
    creds: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if creds:
        return creds.credentials
    return cookie_token


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _resolve_token(creds, access_token)
    user = _extract_user(token, db, required=True)
    assert user is not None
    return user


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    token = _resolve_token(creds, access_token)
    return _extract_user(token, db, required=False)


def require_role(role_name: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        roles = get_user_roles(db, current_user.id)
        if "master" in roles or role_name in roles:
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return dependency


def is_admin_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> bool:
    """Check if the current request is from a master or admin user."""
    token = _resolve_token(creds, access_token)
    if not token:
        return False
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return False
    user = get_user_by_id(db, int(payload["sub"]))
    if not user or user.status != 0:
        return False
    roles = get_user_roles(db, user.id)
    return "master" in roles or "admin" in roles


def require_feature(flag_name: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        roles = get_user_roles(db, current_user.id)
        if "master" in roles:
            return current_user
        features = get_user_features(db, current_user.id)
        if flag_name in features:
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Feature not available")
    return dependency
