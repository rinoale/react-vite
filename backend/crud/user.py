from sqlalchemy.orm import Session

from db.models import User, Role, UserRole, FeatureFlag, RoleFeatureFlag


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_discord_id(db: Session, discord_id: str) -> User | None:
    return db.query(User).filter(User.discord_id == discord_id).first()


def get_user_by_id(db: Session, user_id) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, *, email: str, password_hash: str | None = None,
                discord_id: str | None = None, discord_username: str | None = None) -> User:
    user = User(email=email, password_hash=password_hash,
                discord_id=discord_id, discord_username=discord_username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_profile(db: Session, user: User, *, server: str | None = None, game_id: str | None = None) -> User:
    if server is not None:
        user.server = server
    if game_id is not None:
        user.game_id = game_id
    db.commit()
    db.refresh(user)
    return user


def link_discord(db: Session, user: User, discord_id: str, discord_username: str) -> User:
    user.discord_id = discord_id
    user.discord_username = discord_username
    db.commit()
    db.refresh(user)
    return user


def get_user_roles(db: Session, user_id) -> list[str]:
    rows = db.query(Role.name).join(UserRole).filter(UserRole.user_id == user_id).all()
    return [r[0] for r in rows]


def get_user_features(db: Session, user_id) -> list[str]:
    rows = (
        db.query(FeatureFlag.name)
        .join(RoleFeatureFlag)
        .join(Role)
        .join(UserRole)
        .filter(UserRole.user_id == user_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def assign_role(db: Session, user_id, role_name: str) -> bool:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        return False
    existing = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role.id).first()
    if existing:
        return True
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.commit()
    return True


def remove_role(db: Session, user_id, role_name: str) -> bool:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        return False
    row = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role.id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def assign_feature_to_role(db: Session, role_name: str, flag_name: str) -> bool:
    role = db.query(Role).filter(Role.name == role_name).first()
    flag = db.query(FeatureFlag).filter(FeatureFlag.name == flag_name).first()
    if not role or not flag:
        return False
    existing = db.query(RoleFeatureFlag).filter(
        RoleFeatureFlag.role_id == role.id, RoleFeatureFlag.feature_flag_id == flag.id
    ).first()
    if existing:
        return True
    db.add(RoleFeatureFlag(role_id=role.id, feature_flag_id=flag.id))
    db.commit()
    return True


def remove_feature_from_role(db: Session, role_name: str, flag_name: str) -> bool:
    role = db.query(Role).filter(Role.name == role_name).first()
    flag = db.query(FeatureFlag).filter(FeatureFlag.name == flag_name).first()
    if not role or not flag:
        return False
    row = db.query(RoleFeatureFlag).filter(
        RoleFeatureFlag.role_id == role.id, RoleFeatureFlag.feature_flag_id == flag.id
    ).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
