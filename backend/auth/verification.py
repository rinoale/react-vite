from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User
from auth.dependencies import get_current_user
from auth.services.verification_service import request_verification

router = APIRouter()


@router.post("/verify/request")
def request_verify(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = request_verification(user_id=current_user.id, db=db)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result
