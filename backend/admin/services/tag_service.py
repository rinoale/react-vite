from typing import Optional, Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import models
from admin.schemas.tags import TagCreate, BulkTagCreate


_ENTITY_NAME_COLUMN = {
    'reforge_options':      'option_name',
    'echostone_options':    'option_name',
    'murias_relic_options': 'option_name',
    'game_items':           'name',
    'listings':             'name',
    'enchants':             'name',
}

_DISPLAY_NAME_CASE = "CASE tt.target_type\n" + "\n".join(
    f"                    WHEN '{tbl}' THEN (SELECT x.{col} FROM {tbl} x WHERE x.id = tt.target_id)"
    for tbl, col in _ENTITY_NAME_COLUMN.items()
) + "\n                END"

_TAG_POSITION_WEIGHTS = [80, 60, 30]

_UNIQUE_TAGS_SORT_MAP = {
    "name": "t.name",
    "-name": "t.name DESC",
    "target_count": "target_count",
    "-target_count": "target_count DESC",
    "weight": "t.weight",
    "-weight": "t.weight DESC",
    "created_at": "t.created_at",
    "-created_at": "t.created_at DESC",
}


def _get_or_create_tag(*, name: str, weight: int = 0, db: Session):
    tag = db.query(models.Tag).filter(models.Tag.name == name).first()
    if tag:
        return tag
    tag = models.Tag(name=name, weight=weight)
    db.add(tag)
    db.flush()
    return tag


def get_tags(*, target_type: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session):
    where = "WHERE tt.target_type = :target_type" if target_type else ""
    params = {"limit": limit, "offset": offset}
    if target_type:
        params["target_type"] = target_type
    rows = db.execute(
        text(f"""
            SELECT
                tt.id, t.id AS tag_id, tt.target_type, tt.target_id,
                t.name, t.weight,
                {_DISPLAY_NAME_CASE} AS target_display_name
            FROM tag_targets tt
            JOIN tags t ON t.id = tt.tag_id
            {where}
            ORDER BY tt.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def create_tag(*, data: TagCreate, db: Session):
    tag = _get_or_create_tag(db=db, name=data.name, weight=data.weight)
    tt = models.TagTarget(
        tag_id=tag.id,
        target_type=data.target_type,
        target_id=data.target_id,
    )
    db.add(tt)
    try:
        db.commit()
        db.refresh(tt)
    except IntegrityError:
        db.rollback()
        return None
    return tt


def delete_tag(*, tag_target_id, db: Session):
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    db.delete(tt)
    db.commit()
    return True


def search_entities(*, target_type: str, q: str, limit: int = 20, like: bool = True, db: Session):
    if target_type not in _ENTITY_NAME_COLUMN:
        return []
    tbl, col = target_type, _ENTITY_NAME_COLUMN[target_type]
    q_param = f"%{q}%" if like else q
    rows = db.execute(
        text(f"""
            SELECT id, {col} AS name
            FROM {tbl}
            WHERE {col} ILIKE :q
            ORDER BY {col}
            LIMIT :limit
        """),
        {"q": q_param, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def bulk_create_tags(*, data: BulkTagCreate, db: Session):
    created = 0
    duplicates = 0
    seen = set()
    explicit_weight = data.weight
    for i, name in enumerate(data.names):
        if name in seen:
            continue
        seen.add(name)
        existing = db.query(models.Tag).filter(models.Tag.name == name).first()
        if explicit_weight is not None:
            tag = existing or models.Tag(name=name, weight=explicit_weight)
            if not existing:
                db.add(tag)
                db.flush()
            weight = 0
        else:
            pos_weight = _TAG_POSITION_WEIGHTS[i] if i < len(_TAG_POSITION_WEIGHTS) else 0
            if existing:
                tag = existing
                weight = max(0, pos_weight - tag.weight)
            else:
                tag = models.Tag(name=name, weight=0)
                db.add(tag)
                db.flush()
                weight = pos_weight
        if not data.targets:
            if not existing:
                created += 1
            else:
                duplicates += 1
            continue
        for target in data.targets:
            sp = db.begin_nested()
            tt = models.TagTarget(
                tag_id=tag.id,
                target_type=target.target_type,
                target_id=target.target_id,
                weight=weight,
            )
            db.add(tt)
            try:
                sp.commit()
                created += 1
            except IntegrityError:
                sp.rollback()
                duplicates += 1
    db.commit()
    return {"created": created, "duplicates": duplicates}


def get_unique_tags(*, limit: int = 100, offset: int = 0,
                    q: Optional[str] = None, sort: Optional[str] = None, db: Session):
    where = ""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if q:
        where = "WHERE t.name ILIKE :q"
        params["q"] = f"%{q}%"
    order = _UNIQUE_TAGS_SORT_MAP.get(sort, "t.id DESC")
    rows = db.execute(
        text(f"""
            SELECT t.id, t.name, t.weight, t.created_at, COUNT(tt.id) AS target_count
            FROM tags t
            LEFT JOIN tag_targets tt ON tt.tag_id = t.id
            {where}
            GROUP BY t.id
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def delete_tag_by_id(*, tag_id, db: Session):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    db.delete(tag)
    db.commit()
    return True


def get_tag_detail(*, tag_id, db: Session):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return None
    rows = db.execute(
        text(f"""
            SELECT
                tt.id, tt.target_type, tt.target_id, tt.weight,
                {_DISPLAY_NAME_CASE} AS target_display_name
            FROM tag_targets tt
            WHERE tt.tag_id = :tag_id
            ORDER BY tt.id
        """),
        {"tag_id": tag_id},
    ).mappings()
    return {
        "id": tag.id,
        "name": tag.name,
        "weight": tag.weight,
        "targets": [dict(r) for r in rows],
    }


def update_tag_weight(*, tag_id, weight: int, db: Session):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    tag.weight = weight
    db.commit()
    return True


def bulk_update_tag_target_weights(*, ids: list, weight: int, db: Session):
    updated = db.query(models.TagTarget).filter(models.TagTarget.id.in_(ids)).update(
        {"weight": weight}, synchronize_session="fetch"
    )
    db.commit()
    return {"updated": updated}


def update_tag_target_weight(*, tag_target_id, weight: int, db: Session):
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    tt.weight = weight
    db.commit()
    return True
