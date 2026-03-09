from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import logging
import os
from admin import router as admin_router
from auth import router as auth_router
from auth.dependencies import is_admin_user
from corrections import router as corrections_router
from misc import router as misc_router
from trade import router as trade_router
from core.config import get_settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'backend.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('mabinogi')

# Route uvicorn's access & error logs to the same file
for name in ('uvicorn', 'uvicorn.access', 'uvicorn.error'):
    uv_logger = logging.getLogger(name)
    uv_logger.handlers = logging.getLogger().handlers
    uv_logger.propagate = False

settings = get_settings()

app = FastAPI()

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')
_ADMIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend-admin')
_SPA_MODE = os.path.isdir(_FRONTEND_DIR)

_api_prefix = "/api" if _SPA_MODE else ""
api = APIRouter(prefix=_api_prefix)
api.include_router(auth_router)
api.include_router(admin_router)
api.include_router(corrections_router)
api.include_router(misc_router)
api.include_router(trade_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# SPA static file serving (must be after API routers)
# ---------------------------------------------------------------------------
if _SPA_MODE:
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIR, "assets")), name="assets")

    if os.path.isdir(_ADMIN_DIR):
        app.mount("/admin/assets", StaticFiles(directory=os.path.join(_ADMIN_DIR, "assets")), name="admin-assets")

        @app.get("/admin/{path:path}")
        async def admin_spa_fallback(request: Request, path: str, allowed: bool = Depends(is_admin_user)):
            file_path = os.path.join(_ADMIN_DIR, path)
            if path and os.path.isfile(file_path):
                return FileResponse(file_path)
            if not allowed:
                return RedirectResponse("/")
            return FileResponse(os.path.join(_ADMIN_DIR, "index.html"))

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        if path == "admin":
            return RedirectResponse("/admin/")
        file_path = os.path.join(_FRONTEND_DIR, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"message": "Mabinogi Item Trade API is running"}
