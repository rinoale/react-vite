from fastapi import APIRouter

from admin.data import router as data_router
from admin.listings import router as listings_router
from admin.tags import router as tags_router
from admin.users import router as users_router
from admin.validate import router as validate_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(data_router)
router.include_router(listings_router)
router.include_router(tags_router)
router.include_router(users_router)
router.include_router(validate_router)

__all__ = ["router"]
