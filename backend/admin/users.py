from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User
from crud import user as crud_user
from auth.dependencies import require_role

router = APIRouter()

_master_required = Depends(require_role("master"))


@router.get("/users")
def admin_list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    from db.models import User as UserModel
    users = db.query(UserModel).order_by(UserModel.id).offset(offset).limit(limit).all()
    return {
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "id": u.id,
                "email": u.email,
                "discord_username": u.discord_username,
                "server": u.server,
                "game_id": u.game_id,
                "status": u.status,
                "verified": u.verified,
                "created_at": u.created_at,
                "roles": crud_user.get_user_roles(db, u.id),
                "features": crud_user.get_user_features(db, u.id),
            }
            for u in users
        ],
    }


@router.get("/roles")
def admin_list_roles(db: Session = Depends(get_db), _: User = _master_required):
    from db.models import Role, RoleFeatureFlag, FeatureFlag
    roles = db.query(Role).order_by(Role.id).all()
    result = []
    for role in roles:
        flags = (
            db.query(FeatureFlag.name)
            .join(RoleFeatureFlag)
            .filter(RoleFeatureFlag.role_id == role.id)
            .all()
        )
        result.append({"id": role.id, "name": role.name, "features": [f[0] for f in flags]})
    return result


@router.get("/feature-flags")
def admin_list_feature_flags(db: Session = Depends(get_db), _: User = _master_required):
    from db.models import FeatureFlag
    flags = db.query(FeatureFlag).order_by(FeatureFlag.id).all()
    return [{"id": f.id, "name": f.name} for f in flags]


@router.post("/users/{user_id}/roles/{role_name}")
def admin_assign_role(
    user_id: int, role_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.assign_role(db, user_id, role_name):
        raise HTTPException(status_code=404, detail="User or role not found")
    return {"ok": True}


@router.delete("/users/{user_id}/roles/{role_name}")
def admin_remove_role(
    user_id: int, role_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.remove_role(db, user_id, role_name):
        raise HTTPException(status_code=404, detail="User role not found")
    return {"ok": True}


@router.post("/roles/{role_name}/features/{flag_name}")
def admin_assign_feature(
    role_name: str, flag_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.assign_feature_to_role(db, role_name, flag_name):
        raise HTTPException(status_code=404, detail="Role or feature flag not found")
    return {"ok": True}


@router.delete("/roles/{role_name}/features/{flag_name}")
def admin_remove_feature(
    role_name: str, flag_name: str,
    db: Session = Depends(get_db),
    _: User = _master_required,
):
    if not crud_user.remove_feature_from_role(db, role_name, flag_name):
        raise HTTPException(status_code=404, detail="Role feature flag not found")
    return {"ok": True}
