from sqlalchemy import Column, Integer, String, SmallInteger, Boolean, Numeric, ForeignKey, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .connector import Base

class Enchant(Base):
    __tablename__ = "enchants"

    id = Column(Integer, primary_key=True, index=True)
    slot = Column(SmallInteger, nullable=False)  # 0=접두, 1=접미
    name = Column(Text, nullable=False)
    rank = Column(SmallInteger, nullable=False)  # 1..15
    header_text = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    effects = relationship("EnchantEffect", back_populates="enchant", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('name', 'rank', 'slot', name='_enchant_name_rank_slot_uc'),
    )

class Effect(Base):
    __tablename__ = "effects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    is_pct = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enchant_links = relationship("EnchantEffect", back_populates="effect_def")

class EnchantEffect(Base):
    __tablename__ = "enchant_effects"

    id = Column(Integer, primary_key=True, index=True)
    enchant_id = Column(Integer, ForeignKey("enchants.id", ondelete="CASCADE"), nullable=False)
    effect_id = Column(Integer, ForeignKey("effects.id", ondelete="RESTRICT"), nullable=True)
    effect_order = Column(Integer, nullable=False)
    condition_text = Column(Text, nullable=True)
    min_value = Column(Numeric, nullable=True)
    max_value = Column(Numeric, nullable=True)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enchant = relationship("Enchant", back_populates="effects")
    effect_def = relationship("Effect", back_populates="enchant_links")

    __table_args__ = (
        UniqueConstraint('enchant_id', 'effect_order', name='_enchant_effect_order_uc'),
    )

class ReforgeOption(Base):
    __tablename__ = "reforge_options"

    id = Column(Integer, primary_key=True, index=True)
    option_name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enchants = relationship("ItemEnchant", back_populates="item", cascade="all, delete-orphan")

class ItemEnchant(Base):
    __tablename__ = "item_enchants"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    enchant_id = Column(Integer, ForeignKey("enchants.id", ondelete="RESTRICT"), nullable=False)
    slot = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item", back_populates="enchants")
    enchant = relationship("Enchant")

    __table_args__ = (
        UniqueConstraint('item_id', 'slot', name='_item_slot_uc'),
    )
