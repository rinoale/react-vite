from fastapi import APIRouter, Depends

from auth.dependencies import admin_gate
from admin.system_log import enable_audit  # noqa: F401 — registers SQLAlchemy event listener on import
from admin.activity import router as activity_router
from admin.data import router as data_router
from admin.jobs import router as jobs_router
from admin.listings import router as listings_router
from admin.tags import router as tags_router
from admin.usage import router as usage_router
from admin.usage_oci import router as usage_oci_router
from admin.users import router as users_router
from admin.auto_tag_rules import router as auto_tag_rules_router
from admin.system_logs import router as system_logs_router
from admin.validate import router as validate_router

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_gate), Depends(enable_audit)])
router.include_router(activity_router)
router.include_router(auto_tag_rules_router)
router.include_router(data_router)
router.include_router(jobs_router)
router.include_router(listings_router)
router.include_router(tags_router)
router.include_router(usage_router)
router.include_router(usage_oci_router)
router.include_router(users_router)
router.include_router(system_logs_router)
router.include_router(validate_router)

__all__ = ["router"]
