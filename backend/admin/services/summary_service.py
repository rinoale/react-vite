from sqlalchemy.orm import Session
from db import models


def get_summary(*, db: Session):
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
