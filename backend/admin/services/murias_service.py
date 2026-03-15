from typing import Optional

from sqlalchemy.orm import Session

from db import models


def get_murias_relic_options(*, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session):
    query = db.query(models.MuriasRelicOption)
    if id:
        query = query.filter(models.MuriasRelicOption.id == id)
    elif q:
        query = query.filter(models.MuriasRelicOption.option_name.ilike(f"%{q}%"))
    return query.order_by(models.MuriasRelicOption.id).limit(limit).offset(offset).all()
