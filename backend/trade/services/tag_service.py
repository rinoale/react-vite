from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db.models import Tag, TagTarget
from lib.utils.log import logger

_TAG_POSITION_WEIGHTS = [80, 60, 30]
_SPECIAL_UPGRADE_NAMES = {'R': '붉개', 'S': '푸개'}


def _get_or_create_tag(db, name, weight=0):
    """Get existing tag or create a new one. Handles concurrent insert race."""
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag:
        return tag
    sp = db.begin_nested()
    tag = Tag(name=name, weight=weight)
    db.add(tag)
    try:
        sp.commit()
    except IntegrityError:
        sp.rollback()
        tag = db.query(Tag).filter(Tag.name == name).first()
    return tag


def _attach_tag(db, tag, target_type, target_id, weight):
    """Attach a tag to a target. Silently skips duplicates."""
    sp = db.begin_nested()
    db.add(TagTarget(
        tag_id=tag.id,
        target_type=target_type,
        target_id=target_id,
        weight=weight,
    ))
    try:
        sp.commit()
    except IntegrityError:
        sp.rollback()


def create_listing_tags(listing, payload, db):
    """Create user-submitted and auto-generated tags for a listing.

    User tags use positional weights [80, 60, 30].
    Auto tags (enchant, erg, special upgrade) use weight 0.
    Deduplicates: auto tags already attached by user tags are skipped.
    """
    try:
        attached = set()

        # --- User-submitted tags (positional weights) ---
        for i, tag_name in enumerate(payload.tags[:3]):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            pos_weight = _TAG_POSITION_WEIGHTS[i] if i < len(_TAG_POSITION_WEIGHTS) else 0
            tag = _get_or_create_tag(db, tag_name)
            weight = max(0, pos_weight - tag.weight)
            _attach_tag(db, tag, 'listing', listing.id, weight)
            attached.add(tag_name)

        # --- Auto tags (skip if already attached by user) ---
        auto_tags = _build_auto_tags(payload, db)
        for name in auto_tags:
            if name in attached:
                continue
            tag = _get_or_create_tag(db, name)
            _attach_tag(db, tag, 'listing', listing.id, 0)

        db.commit()
        logger.info("register-listing  tags created for listing id=%d user=%d auto=%d",
                     listing.id, min(len(payload.tags), 3), len(auto_tags))
    except Exception:
        db.rollback()
        logger.exception("register-listing  tag creation failed for listing id=%d", listing.id)


def _build_auto_tags(payload, db):
    """Build list of auto-generated tag names from structured listing data."""
    tags = []
    _tag_enchant_names(tags, payload)
    _tag_erg(tags, payload)
    _tag_special_upgrade(tags, payload)
    _tag_piercing_maxroll(tags, payload, db)
    return tags


def _tag_enchant_names(tags, payload):
    for enc in payload.enchants:
        if enc.name:
            tags.append(enc.name)


def _tag_erg(tags, payload):
    if payload.erg_grade and payload.erg_level == 50:
        tags.append(f'{payload.erg_grade}르그50')


def _tag_special_upgrade(tags, payload):
    if not payload.special_upgrade_type:
        return
    upgrade_name = _SPECIAL_UPGRADE_NAMES.get(payload.special_upgrade_type)
    if upgrade_name:
        tags.append(upgrade_name)
    if payload.special_upgrade_level in (7, 8):
        tags.append(f'{payload.special_upgrade_level}강')


def _tag_piercing_maxroll(tags, payload, db):
    for opt in payload.listing_options:
        if opt.option_type != 'enchant_effects' or opt.option_name != '피어싱 레벨':
            continue
        if opt.rolled_value is None or not opt.option_id:
            continue
        row = db.execute(
            text("SELECT max_value FROM enchant_effects WHERE id = :id"),
            {"id": opt.option_id},
        ).mappings().first()
        if row and row['max_value'] is not None and float(opt.rolled_value) >= float(row['max_value']):
            tags.append('풀피어싱')
            return
