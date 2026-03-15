from fastapi import APIRouter

from trade.routes.listings import router as listings_router
from trade.routes.examine import router as examine_router
from trade.routes.game_items import router as game_items_router
from trade.routes.tags import router as tags_router

router = APIRouter(tags=["trade"])
router.include_router(listings_router)
router.include_router(examine_router)
router.include_router(game_items_router)
router.include_router(tags_router)

__all__ = ["router"]
