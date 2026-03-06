from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import User
from auth.service import (
    create_token_pair, decode_token,
    get_discord_auth_url, exchange_discord_code,
)
from auth.dependencies import get_current_user
from auth.cookies import set_auth_cookies, clear_auth_cookies
from core.config import get_settings
from crud.user import (
    get_user_by_email, get_user_by_discord_id, create_user,
    update_user_profile, link_discord,
    get_user_roles, get_user_features,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_user_out(db: Session, user: User) -> schemas.UserOut:
    roles = get_user_roles(db, user.id)
    features = get_user_features(db, user.id)
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        discord_username=user.discord_username,
        server=user.server,
        game_id=user.game_id,
        status=user.status,
        verified=user.verified,
        roles=roles,
        features=features,
    )


def _set_tokens(response: Response, user_id: int):
    tokens = create_token_pair(user_id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])


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
    from crud.user import get_user_by_id
    user = get_user_by_id(db, int(payload["sub"]))
    if not user or user.status != 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
    _set_tokens(response, user.id)
    return {"ok": True}


@router.get("/discord")
def discord_auth():
    return RedirectResponse(url=get_discord_auth_url())


@router.get("/discord/callback")
async def discord_callback(code: str, db: Session = Depends(get_db)):
    settings = get_settings()
    frontend_url = settings.frontend_url

    discord_user = await exchange_discord_code(code)
    if not discord_user:
        return RedirectResponse(url=f"{frontend_url}/login?error=discord_failed")

    discord_id = discord_user["id"]
    discord_username = discord_user.get("username", "")
    email = discord_user.get("email")

    user = get_user_by_discord_id(db, discord_id)
    if not user:
        if email:
            user = get_user_by_email(db, email)
            if user:
                link_discord(db, user, discord_id, discord_username)
        if not user and not email:
            return RedirectResponse(url=f"{frontend_url}/login?error=no_email")
        if not user:
            user = create_user(db, email=email, discord_id=discord_id, discord_username=discord_username)

    tokens = create_token_pair(user.id)
    redirect = RedirectResponse(url=f"{frontend_url}/login?auth=success")
    set_auth_cookies(redirect, tokens["access_token"], tokens["refresh_token"])
    return redirect


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _build_user_out(db, current_user)


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    body: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_user_profile(db, current_user, server=body.server, game_id=body.game_id)
    return _build_user_out(db, current_user)
