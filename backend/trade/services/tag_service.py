from sqlalchemy.exc import IntegrityError

from db.connector import SessionLocal
from db.models import Tag, TagTarget
from lib.utils.log import logger
from trade.services.auto_tag_engine import evaluate_rules

_TAG_POSITION_WEIGHTS = [80, 60, 30]


def _get_or_create_tag(*, name, weight=0, db):
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


def _attach_tag(*, tag, target_type, target_id, weight, db):
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


def create_listing_tags(*, listing_id, tags, payload):
    """Create user-submitted and auto-generated tags for a listing.

    Uses its own DB session — designed for BackgroundTasks (after response).
    User tags use positional weights [80, 60, 30].
    Auto tags use weight 0.
    Deduplicates: auto tags already attached by user tags are skipped.
    """
    db = SessionLocal()
    try:
        attached = set()

        # --- User-submitted tags (positional weights) ---
        for i, tag_name in enumerate(tags[:3]):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            pos_weight = _TAG_POSITION_WEIGHTS[i] if i < len(_TAG_POSITION_WEIGHTS) else 0
            tag = _get_or_create_tag(name=tag_name, db=db)
            weight = max(0, pos_weight - tag.weight)
            _attach_tag(tag=tag, target_type='listings', target_id=listing_id, weight=weight, db=db)
            attached.add(tag_name)

        # --- Auto tags (skip if already attached by user) ---
        auto_tags = evaluate_rules(payload=payload, db=db)
        for name in auto_tags:
            if name in attached:
                continue
            tag = _get_or_create_tag(name=name, db=db)
            _attach_tag(tag=tag, target_type='listings', target_id=listing_id, weight=0, db=db)

        db.commit()
        logger.info("register-listing  tags created for listing id=%s user=%d auto=%d",
                     listing_id, min(len(tags), 3), len(auto_tags))
    except Exception:
        db.rollback()
        logger.exception("register-listing  tag creation failed for listing id=%s", listing_id)
    finally:
        db.close()
