from fastapi import Response

from core.config import get_settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    settings = get_settings()
    for key, value, max_age in (
        ("access_token", access_token, settings.access_token_expire_minutes * 60),
        ("refresh_token", refresh_token, settings.refresh_token_expire_days * 86400),
    ):
        response.set_cookie(
            key=key,
            value=value,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            max_age=max_age,
            path="/",
        )


def clear_auth_cookies(response: Response):
    settings = get_settings()
    for key in ("access_token", "refresh_token"):
        response.delete_cookie(
            key=key,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/",
        )
