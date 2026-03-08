from fastapi import APIRouter, HTTPException, Query

from lib.utils.log import logger
from lib.api.nexon_open_api import get_horn_bugle_history

router = APIRouter()


@router.get("/horn-bugle")
def horn_bugle(server_name: str = Query(default="류트")):
    try:
        return get_horn_bugle_history(server_name)
    except Exception as e:
        logger.exception("horn-bugle fetch failed")
        raise HTTPException(status_code=502, detail=str(e))
