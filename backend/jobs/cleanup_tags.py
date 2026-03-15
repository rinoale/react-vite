from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import Tag, SystemLog


def cleanup_zero_weight_tags(db: Session, *, payload: dict | None = None) -> str:
    """Delete tags with weight 0 that have no active listing attachments.

    A tag is cleaned up when:
    - Tag.weight == 0 (no admin-assigned global weight)
    - AND it has no tag_targets, OR all its tag_targets point to
      listings that are sold (2) or deleted (3)
    """
    rows = db.execute(text("""
        SELECT t.id, t.name FROM tags t
        WHERE t.weight = 0
          AND NOT EXISTS (
            SELECT 1 FROM tag_targets tt
            JOIN listings l ON l.id = tt.target_id AND tt.target_type = 'listings'
            WHERE tt.tag_id = t.id
              AND l.status NOT IN (2, 3)
          )
    """)).all()
    if rows:
        ids = [r.id for r in rows]
        names = [r.name for r in rows]
        db.query(Tag).filter(Tag.id.in_(ids)).delete(synchronize_session=False)
        db.add(SystemLog(
            source='system',
            action='job:cleanup_zero_weight_tags',
            before_={'tags': names},
            after_=None,
        ))
    db.commit()
    return f"Deleted {len(rows)} orphaned tags with weight 0"
