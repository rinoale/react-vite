from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas, models

router = APIRouter()


@router.get("/auto-tag-rules")
def list_rules(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.AutoTagRule)
        .order_by(models.AutoTagRule.priority, models.AutoTagRule.id)
        .limit(limit).offset(offset).all()
    )
    return {"limit": limit, "offset": offset, "rows": [schemas.AutoTagRuleOut.model_validate(r) for r in rows]}


@router.get("/auto-tag-rules/{rule_id}", response_model=schemas.AutoTagRuleOut)
def get_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
):
    rule = db.query(models.AutoTagRule).filter(models.AutoTagRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("/auto-tag-rules", response_model=schemas.AutoTagRuleOut)
def create_rule(
    data: schemas.AutoTagRuleCreate,
    db: Session = Depends(get_db),
):
    rule = models.AutoTagRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/auto-tag-rules/{rule_id}", response_model=schemas.AutoTagRuleOut)
def update_rule(
    rule_id: UUID,
    data: schemas.AutoTagRuleUpdate,
    db: Session = Depends(get_db),
):
    rule = db.query(models.AutoTagRule).filter(models.AutoTagRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, val)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/auto-tag-rules/{rule_id}")
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
):
    rule = db.query(models.AutoTagRule).filter(models.AutoTagRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": True}
