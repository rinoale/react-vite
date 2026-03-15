from fastapi import APIRouter

from auth.discord import router as discord_router
from auth.session import router as session_router
from auth.profile import router as profile_router
from auth.verification import router as verification_router

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(discord_router)
router.include_router(session_router)
router.include_router(profile_router)
router.include_router(verification_router)

__all__ = ["router"]
