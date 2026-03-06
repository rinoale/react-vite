from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from db.models import User
from auth.service import (
    hash_password, verify_password, create_token_pair,
    decode_token, get_discord_auth_url, exchange_discord_code,
)
from auth.dependencies import get_current_user
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


@router.post("/register", response_model=schemas.TokenResponse)
def register(body: schemas.UserRegister, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = create_user(db, email=body.email, password_hash=hash_password(body.password))
    return create_token_pair(user.id)


@router.post("/login", response_model=schemas.TokenResponse)
def login(body: schemas.UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    return create_token_pair(user.id)


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(body: schemas.RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    from crud.user import get_user_by_id
    user = get_user_by_id(db, int(payload["sub"]))
    if not user or user.status != 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
    return create_token_pair(user.id)


@router.get("/discord")
def discord_auth():
    return RedirectResponse(url=get_discord_auth_url())


@router.get("/discord/callback")
async def discord_callback(code: str, db: Session = Depends(get_db)):
    settings = get_settings()
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:5173"

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
    params = urlencode({"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"]})
    return RedirectResponse(url=f"{frontend_url}/login?{params}")


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
