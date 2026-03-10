from sqlalchemy import Column, Float, Index, Integer, String, SmallInteger, Boolean, Numeric, ForeignKey, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .connector import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=True)
    discord_id = Column(Text, nullable=True, unique=True)
    discord_username = Column(Text, nullable=True)
    server = Column(Text, nullable=True)
    game_id = Column(Text, nullable=True)
    status = Column(SmallInteger, nullable=False, server_default='0')  # 0=active, 1=inactive
    verified = Column(Boolean, nullable=False, server_default='false')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('server', 'game_id', name='_user_server_game_id_uc'),
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_roles = relationship("UserRole", back_populates="role")
    feature_flags = relationship("RoleFeatureFlag", back_populates="role", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='_user_role_uc'),
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role_flags = relationship("RoleFeatureFlag", back_populates="feature_flag")


class RoleFeatureFlag(Base):
    __tablename__ = "role_feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    feature_flag_id = Column(Integer, ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = relationship("Role", back_populates="feature_flags")
    feature_flag = relationship("FeatureFlag", back_populates="role_flags")

    __table_args__ = (
        UniqueConstraint('role_id', 'feature_flag_id', name='_role_feature_flag_uc'),
    )


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
    """
    status: 0=draft, 1=listed, 2=sold, 3=deleted
    """
    __tablename__ = "listings"

    DRAFT = 0
    LISTED = 1
    SOLD = 2
    DELETED = 3

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(SmallInteger, nullable=False, server_default='0', index=True)
    name = Column(Text, nullable=False, index=True)
    description = Column(Text, nullable=True)
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

    user = relationship("User")
    game_item = relationship("GameItem")
    prefix_enchant = relationship("Enchant", foreign_keys=[prefix_enchant_id])
    suffix_enchant = relationship("Enchant", foreign_keys=[suffix_enchant_id])
    listing_options = relationship("ListingOption", back_populates="listing", cascade="all, delete-orphan")

class ListingOption(Base):
    __tablename__ = "listing_options"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    option_type = Column(Text, nullable=False)  # reforge_options, echostone_options, murias_relic_options, enchant_effects
    option_id = Column(Integer, nullable=True)
    option_name = Column(Text, nullable=False)
    rolled_value = Column(Numeric, nullable=True)
    max_level = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", back_populates="listing_options")

    __table_args__ = (
        Index('ix_listing_options_listing_id', 'listing_id'),
        Index('ix_listing_options_target', 'option_type', 'option_id'),
    )


class EchostoneOption(Base):
    __tablename__ = "echostone_options"

    id = Column(Integer, primary_key=True, index=True)
    option_name = Column(Text, nullable=False, unique=True)
    type = Column(Text, nullable=False)  # red, blue, yellow, silver, black
    max_level = Column(Integer, nullable=True)
    min_level = Column(Integer, nullable=False, server_default='1')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MuriasRelicOption(Base):
    __tablename__ = "murias_relic_options"

    id = Column(Integer, primary_key=True, index=True)
    option_name = Column(Text, nullable=False, unique=True)
    type = Column(Text, nullable=False)  # elemental_knight, saint_bard, etc.
    max_level = Column(Integer, nullable=True)
    min_level = Column(Integer, nullable=False, server_default='1')
    value_per_level = Column(Float, nullable=True)
    option_unit = Column(Text, nullable=False, server_default='')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    weight = Column(Integer, nullable=False, server_default='0')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    targets = relationship("TagTarget", back_populates="tag", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_tags_weight', 'weight'),
    )


class TagTarget(Base):
    __tablename__ = "tag_targets"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False, server_default='0')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tag = relationship("Tag", back_populates="targets")

    __table_args__ = (
        UniqueConstraint('tag_id', 'target_type', 'target_id', name='_tag_target_uc'),
        Index('ix_tag_targets_target', 'target_type', 'target_id'),
        Index('ix_tag_targets_tag_id', 'tag_id'),
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, server_default='pending')  # pending, running, completed, failed
    result_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    worker_id = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
