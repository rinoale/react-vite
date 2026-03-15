from fastapi import APIRouter, Depends

from auth.dependencies import admin_gate
from admin.middleware.audit import enable_audit  # noqa: F401 — registers SQLAlchemy event listener on import
from admin.routes.data import router as data_router
from admin.routes.operations import router as operations_router
from admin.routes.system import router as system_router
from admin.routes.validate import router as validate_router

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_gate), Depends(enable_audit)])
router.include_router(data_router)
router.include_router(operations_router)
router.include_router(system_router)
router.include_router(validate_router)

__all__ = ["router"]
