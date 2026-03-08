from fastapi import APIRouter

from misc.horn_bugle import router as horn_bugle_router

router = APIRouter(prefix="/misc", tags=["misc"])
router.include_router(horn_bugle_router)

__all__ = ["router"]
