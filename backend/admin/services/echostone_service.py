from typing import Optional

from sqlalchemy.orm import Session

from db import models


def get_echostone_options(*, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session):
    query = db.query(models.EchostoneOption)
    if id:
        query = query.filter(models.EchostoneOption.id == id)
    elif q:
        query = query.filter(models.EchostoneOption.option_name.ilike(f"%{q}%"))
    return query.order_by(models.EchostoneOption.id).limit(limit).offset(offset).all()
