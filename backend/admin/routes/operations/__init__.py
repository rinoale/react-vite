from fastapi import APIRouter

from admin.routes.operations.listings import router as listings_router
from admin.routes.operations.game_items import router as game_items_router
from admin.routes.operations.tags import router as tags_router
from admin.routes.operations.auto_tag_rules import router as auto_tag_rules_router
from admin.routes.operations.corrections import router as corrections_router

router = APIRouter()

router.include_router(listings_router)
router.include_router(game_items_router)
router.include_router(tags_router)
router.include_router(auto_tag_rules_router)
router.include_router(corrections_router)
