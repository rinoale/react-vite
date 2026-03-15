from fastapi import APIRouter

from admin.routes.system.activity import router as activity_router
from admin.routes.system.system_logs import router as system_logs_router
from admin.routes.system.jobs import router as jobs_router
from admin.routes.system.users import router as users_router
from admin.routes.system.usage import router as usage_router

router = APIRouter()

router.include_router(activity_router)
router.include_router(system_logs_router)
router.include_router(jobs_router)
router.include_router(users_router)
router.include_router(usage_router)
