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
    restriction = Column(Text, nullable=True)
    binding = Column(Boolean, nullable=False, default=False, server_default='false')
    guaranteed_success = Column(Boolean, nullable=False, default=False, server_default='false')
    activation = Column(Text, nullable=True)
    credit = Column(Text, nullable=True)

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
    is_stitched = Column(Boolean, default=False)  # continuation stitch: crop is merged from multiple lines
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trained_version = Column(Text, nullable=True)


class GameItem(Base):
    __tablename__ = "game_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    price = Column(Integer, nullable=True)
    game_item_id = Column(Integer, ForeignKey("game_items.id", ondelete="SET NULL"), nullable=True)
    prefix_enchant_id = Column(Integer, ForeignKey("enchants.id", ondelete="SET NULL"), nullable=True)
    suffix_enchant_id = Column(Integer, ForeignKey("enchants.id", ondelete="SET NULL"), nullable=True)
    item_type = Column(Text, nullable=True)
    item_grade = Column(Text, nullable=True)
    erg_grade = Column(Text, nullable=True)
    erg_level = Column(Integer, nullable=True)
    special_upgrade_type = Column(Text, nullable=True)
    special_upgrade_level = Column(Integer, nullable=True)
    damage = Column(Integer, nullable=True)
    magic_damage = Column(Integer, nullable=True)
    additional_damage = Column(Integer, nullable=True)
    balance = Column(Integer, nullable=True)
    defense = Column(Integer, nullable=True)
    protection = Column(Integer, nullable=True)
    magic_defense = Column(Integer, nullable=True)
    magic_protection = Column(Integer, nullable=True)
    durability = Column(Integer, nullable=True)
    piercing_level = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    game_item = relationship("GameItem")
    prefix_enchant = relationship("Enchant", foreign_keys=[prefix_enchant_id])
    suffix_enchant = relationship("Enchant", foreign_keys=[suffix_enchant_id])
    enchant_effects = relationship("ListingEnchantEffect", back_populates="listing", cascade="all, delete-orphan")
    reforge_options = relationship("ListingReforgeOption", back_populates="listing", cascade="all, delete-orphan")

class ListingEnchantEffect(Base):
    __tablename__ = "listing_enchant_effects"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    enchant_effect_id = Column(Integer, ForeignKey("enchant_effects.id", ondelete="RESTRICT"), nullable=False)
    value = Column(Numeric, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", back_populates="enchant_effects")
    enchant_effect = relationship("EnchantEffect")

class ListingReforgeOption(Base):
    __tablename__ = "listing_reforge_options"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    reforge_option_id = Column(Integer, ForeignKey("reforge_options.id", ondelete="RESTRICT"), nullable=True)
    option_name = Column(Text, nullable=False)
    level = Column(Integer, nullable=True)
    max_level = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", back_populates="reforge_options")
    reforge_option = relationship("ReforgeOption")
