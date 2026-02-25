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

class OcrCorrection(Base):
    __tablename__ = "ocr_corrections"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Text, nullable=False, index=True)
    line_index = Column(SmallInteger, nullable=False)
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=True)
    section = Column(Text, nullable=True)
    ocr_model = Column(Text, nullable=True)
    fm_applied = Column(Boolean, default=False)
    status = Column(Text, nullable=False, server_default='pending')
    charset_mismatch = Column(Text, nullable=True)
    image_filename = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trained_version = Column(Text, nullable=True)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enchants = relationship("ItemEnchant", back_populates="item", cascade="all, delete-orphan")
    enchant_effects = relationship("ItemEnchantEffect", back_populates="item", cascade="all, delete-orphan")
    reforge_options = relationship("ItemReforgeOption", back_populates="item", cascade="all, delete-orphan")

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

class ItemEnchantEffect(Base):
    __tablename__ = "item_enchant_effects"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    enchant_effect_id = Column(Integer, ForeignKey("enchant_effects.id", ondelete="RESTRICT"), nullable=False)
    value = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item", back_populates="enchant_effects")
    enchant_effect = relationship("EnchantEffect")

class ItemReforgeOption(Base):
    __tablename__ = "item_reforge_options"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    reforge_option_id = Column(Integer, ForeignKey("reforge_options.id", ondelete="RESTRICT"), nullable=True)
    option_name = Column(Text, nullable=False)
    level = Column(Integer, nullable=True)
    max_level = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item", back_populates="reforge_options")
    reforge_option = relationship("ReforgeOption")
