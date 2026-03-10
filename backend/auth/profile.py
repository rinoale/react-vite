from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.connector import get_db
from db import schemas
from db.models import User
from auth.dependencies import get_current_user
from crud.user import get_user_roles, get_user_features, update_user_profile

router = APIRouter()


def _build_user_out(db: Session, user: User) -> schemas.UserOut:
    roles = get_user_roles(db, user.id)
    features = get_user_features(db, user.id)
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        discord_username=user.discord_username,
        server=user.server,
        game_id=user.game_id,
        status=user.status,
        verified=user.verified,
        roles=roles,
        features=features,
    )


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _build_user_out(db, current_user)


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    body: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        update_user_profile(db, current_user, server=body.server, game_id=body.game_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="game_id_taken")
    return _build_user_out(db, current_user)
