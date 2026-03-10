from sqlalchemy.orm import Session

from db.models import Tag


def cleanup_zero_weight_tags(db: Session, *, payload: dict | None = None) -> str:
    zero_tags = db.query(Tag).filter(Tag.weight == 0).all()
    count = len(zero_tags)
    for tag in zero_tags:
        db.delete(tag)
    db.commit()
    return f"Deleted {count} tags with weight 0"
