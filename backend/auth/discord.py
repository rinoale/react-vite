from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.connector import get_db
from auth.service import create_token_pair, get_discord_auth_url, exchange_discord_code
from auth.cookies import set_auth_cookies
from core.config import get_settings
from auth.services.user_service import get_user_by_email, get_user_by_discord_id, create_user, link_discord

router = APIRouter()


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
