from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from db import models, schemas

def get_summary(db: Session):
    return {
        "enchants": db.query(models.Enchant).count(),
        "effects": db.query(models.Effect).count(),
        "enchant_effects": db.query(models.EnchantEffect).count(),
        "reforge_options": db.query(models.ReforgeOption).count(),
        "echostone_options": db.query(models.EchostoneOption).count(),
        "murias_relic_options": db.query(models.MuriasRelicOption).count(),
        "listings": db.query(models.Listing).count(),
        "game_items": db.query(models.GameItem).count(),
        "tags": db.query(models.Tag).count(),
    }

def get_enchants(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0):
    where = ""
    params = {"limit": limit, "offset": offset}
    if id:
        where = "WHERE e.id = :id"
        params["id"] = id
    elif q:
        where = "WHERE e.name ILIKE :q"
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(f"""
            SELECT e.id, e.slot, e.name, e.rank, e.header_text,
                   COUNT(ee.id) AS effect_count
            FROM enchants e
            LEFT JOIN enchant_effects ee ON ee.enchant_id = e.id
            {where}
            GROUP BY e.id
            ORDER BY e.id
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]

def get_effects(db: Session, limit: int = 100, offset: int = 0):
    return db.query(models.Effect).order_by(models.Effect.id).limit(limit).offset(offset).all()

def get_enchant_effects(db: Session, limit: int = 100, offset: int = 0):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id,
                ee.enchant_id,
                ee.effect_id,
                ee.effect_order,
                ee.condition_text,
                ee.min_value,
                ee.max_value,
                ee.raw_text,
                e.name AS enchant_name,
                f.name AS effect_name
            FROM enchant_effects ee
            JOIN enchants e ON e.id = ee.enchant_id
            LEFT JOIN effects f ON f.id = ee.effect_id
            ORDER BY ee.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]

def get_enchant_effects_by_id(db: Session, enchant_id):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id,
                ee.enchant_id,
                ee.effect_id,
                ee.effect_order,
                ee.condition_text,
                ee.min_value,
                ee.max_value,
                ee.raw_text,
                f.name AS effect_name
            FROM enchant_effects ee
            LEFT JOIN effects f ON f.id = ee.effect_id
            WHERE ee.enchant_id = :enchant_id
            ORDER BY ee.effect_order
            """
        ),
        {"enchant_id": enchant_id},
    ).mappings()
    return [dict(r) for r in rows]

def get_reforge_options(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0):
    query = db.query(models.ReforgeOption)
    if id:
        query = query.filter(models.ReforgeOption.id == id)
    elif q:
        query = query.filter(models.ReforgeOption.option_name.ilike(f"%{q}%"))
    return query.order_by(models.ReforgeOption.id).limit(limit).offset(offset).all()

def get_echostone_options(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0):
    query = db.query(models.EchostoneOption)
    if id:
        query = query.filter(models.EchostoneOption.id == id)
    elif q:
        query = query.filter(models.EchostoneOption.option_name.ilike(f"%{q}%"))
    return query.order_by(models.EchostoneOption.id).limit(limit).offset(offset).all()

def get_murias_relic_options(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0):
    query = db.query(models.MuriasRelicOption)
    if id:
        query = query.filter(models.MuriasRelicOption.id == id)
    elif q:
        query = query.filter(models.MuriasRelicOption.option_name.ilike(f"%{q}%"))
    return query.order_by(models.MuriasRelicOption.id).limit(limit).offset(offset).all()

def get_listings(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0):
    where = ""
    params = {"limit": limit, "offset": offset}
    if id:
        where = "WHERE l.id = :id"
        params["id"] = id
    elif q:
        where = "WHERE l.name ILIKE :q"
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(f"""
            SELECT
                l.id, l.status, l.name, l.description, l.price, l.game_item_id,
                gi.name AS game_item_name,
                pe.name AS prefix_enchant_name,
                se.name AS suffix_enchant_name,
                l.item_type, l.item_grade, l.erg_grade, l.erg_level, l.created_at,
                COUNT(DISTINCT lo.id) AS option_count
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            LEFT JOIN listing_options lo ON lo.listing_id = l.id
            {where}
            GROUP BY l.id, gi.name, pe.name, se.name
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]

def get_listing_count(db: Session):
    return db.query(models.Listing).count()


def get_game_items(db: Session, q: Optional[str] = None, id: Optional[str] = None, limit: int = 20, offset: int = 0):
    if id:
        rows = db.execute(
            text("SELECT id, name, type, searchable, tradable FROM game_items WHERE id = :id"),
            {"id": id},
        ).mappings()
    elif q:
        rows = db.execute(
            text(
                """
                SELECT id, name, type, searchable, tradable
                FROM game_items
                WHERE name ILIKE :q
                ORDER BY name
                LIMIT :limit OFFSET :offset
                """
            ),
            {"q": f"%{q}%", "limit": limit, "offset": offset},
        ).mappings()
    else:
        rows = db.execute(
            text(
                """
                SELECT id, name, type, searchable, tradable
                FROM game_items
                ORDER BY name
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings()
    return [dict(r) for r in rows]

def get_game_item_count(db: Session):
    return db.query(models.GameItem).count()


# --- Tags (normalized: tags + tag_targets) ---

def _get_or_create_tag(db: Session, name: str, weight: int = 0):
    """Get existing tag by name or create a new one. Returns Tag model instance."""
    tag = db.query(models.Tag).filter(models.Tag.name == name).first()
    if tag:
        return tag
    tag = models.Tag(name=name, weight=weight)
    db.add(tag)
    db.flush()
    return tag


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


def get_tags(db: Session, target_type: Optional[str] = None, limit: int = 100, offset: int = 0):
    where = "WHERE tt.target_type = :target_type" if target_type else ""
    params = {"limit": limit, "offset": offset}
    if target_type:
        params["target_type"] = target_type
    rows = db.execute(
        text(f"""
            SELECT
                tt.id,
                t.id AS tag_id,
                tt.target_type,
                tt.target_id,
                t.name,
                t.weight,
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


def create_tag(db: Session, data: schemas.TagCreate):
    """Get-or-create tag definition (weight on tags table), then attach to the target."""
    tag = _get_or_create_tag(db, data.name, data.weight)
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


def delete_tag(db: Session, tag_target_id):
    """Delete a tag-target association."""
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    db.delete(tt)
    db.commit()
    return True


def search_entities(db: Session, target_type: str, q: str, limit: int = 20, like: bool = True):
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


_TAG_POSITION_WEIGHTS = [80, 60, 30]


def bulk_create_tags(db: Session, data: schemas.BulkTagCreate):
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


def get_unique_tags(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    q: Optional[str] = None,
    sort: Optional[str] = None,
):
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


def delete_tag_by_id(db: Session, tag_id):
    """Delete a tag and all its tag_targets (via CASCADE)."""
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    db.delete(tag)
    db.commit()
    return True


def get_tag_detail(db: Session, tag_id):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return None
    rows = db.execute(
        text(f"""
            SELECT
                tt.id,
                tt.target_type,
                tt.target_id,
                tt.weight,
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


def update_tag_weight(db: Session, tag_id, weight: int):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    tag.weight = weight
    db.commit()
    return True


def bulk_update_tag_target_weights(db: Session, ids: list, weight: int):
    updated = db.query(models.TagTarget).filter(models.TagTarget.id.in_(ids)).update(
        {"weight": weight}, synchronize_session="fetch"
    )
    db.commit()
    return {"updated": updated}


def update_tag_target_weight(db: Session, tag_target_id, weight: int):
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    tt.weight = weight
    db.commit()
    return True
