from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from db.connector import get_db
from auth.service import create_token_pair, decode_token
from auth.cookies import set_auth_cookies, clear_auth_cookies
from crud.user import get_user_by_id

router = APIRouter()


@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = get_user_by_id(db, int(payload["sub"]))
    if not user or user.status != 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
    tokens = create_token_pair(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}
