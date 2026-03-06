from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from admin import router as admin_router
from auth import router as auth_router
from corrections import router as corrections_router
from trade.router import router as trade_router
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
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(corrections_router)
app.include_router(trade_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Mabinogi Item Trade API is running"}
