from fastapi import APIRouter, HTTPException

from admin.services.usage_service import get_r2_usage, get_oci_usage

router = APIRouter()


@router.get("/usage/r2")
async def r2_usage():
    try:
        return await get_r2_usage()
    except ValueError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/usage/oci")
async def oci_usage():
    try:
        return get_oci_usage()
    except ValueError as e:
        raise HTTPException(status_code=501, detail=str(e))
