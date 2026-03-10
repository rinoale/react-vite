"""baseline: all tables

Revision ID: 0001
Revises: -
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Users & Auth ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("discord_id", sa.Text(), nullable=True, unique=True),
        sa.Column("discord_username", sa.Text(), nullable=True),
        sa.Column("server", sa.Text(), nullable=True),
        sa.Column("game_id", sa.Text(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("server", "game_id", name="_user_server_game_id_uc"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "role_id", name="_user_role_uc"),
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "role_feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_flag_id", sa.Integer(), sa.ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("role_id", "feature_flag_id", name="_role_feature_flag_uc"),
    )

    # --- Seed auth data ---
    op.execute("INSERT INTO roles (name) VALUES ('master'), ('admin')")
    op.execute("INSERT INTO feature_flags (name) VALUES ('manage_tags'), ('manage_corrections')")

    # --- Enchants & Effects ---
    op.create_table(
        "enchants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("header_text", sa.Text(), nullable=False, unique=True),
        sa.Column("restriction", sa.Text(), nullable=True),
        sa.Column("binding", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("guaranteed_success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("activation", sa.Text(), nullable=True),
        sa.Column("credit", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", "rank", "slot", name="_enchant_name_rank_slot_uc"),
    )

    op.create_table(
        "effects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("is_pct", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "enchant_effects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("enchant_id", sa.Integer(), sa.ForeignKey("enchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effect_id", sa.Integer(), sa.ForeignKey("effects.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("effect_order", sa.Integer(), nullable=False),
        sa.Column("condition_text", sa.Text(), nullable=True),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("enchant_id", "effect_order", name="_enchant_effect_order_uc"),
    )

    # --- Option master tables ---
    op.create_table(
        "reforge_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("option_name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "echostone_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("option_name", sa.Text(), nullable=False, unique=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("max_level", sa.Integer(), nullable=True),
        sa.Column("min_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "murias_relic_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("option_name", sa.Text(), nullable=False, unique=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("max_level", sa.Integer(), nullable=True),
        sa.Column("min_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("value_per_level", sa.Float(), nullable=True),
        sa.Column("option_unit", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Game items ---
    op.create_table(
        "game_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Listings ---
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("game_item_id", sa.Integer(), sa.ForeignKey("game_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prefix_enchant_id", sa.Integer(), sa.ForeignKey("enchants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suffix_enchant_id", sa.Integer(), sa.ForeignKey("enchants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_type", sa.Text(), nullable=True),
        sa.Column("item_grade", sa.Text(), nullable=True),
        sa.Column("erg_grade", sa.Text(), nullable=True),
        sa.Column("erg_level", sa.Integer(), nullable=True),
        sa.Column("special_upgrade_type", sa.Text(), nullable=True),
        sa.Column("special_upgrade_level", sa.Integer(), nullable=True),
        sa.Column("damage", sa.Integer(), nullable=True),
        sa.Column("magic_damage", sa.Integer(), nullable=True),
        sa.Column("additional_damage", sa.Integer(), nullable=True),
        sa.Column("balance", sa.Integer(), nullable=True),
        sa.Column("defense", sa.Integer(), nullable=True),
        sa.Column("protection", sa.Integer(), nullable=True),
        sa.Column("magic_defense", sa.Integer(), nullable=True),
        sa.Column("magic_protection", sa.Integer(), nullable=True),
        sa.Column("durability", sa.Integer(), nullable=True),
        sa.Column("piercing_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_listings_name", "listings", ["name"])
    op.create_index("ix_listings_user_id", "listings", ["user_id"])

    # --- Listing options (unified polymorphic join) ---
    op.create_table(
        "listing_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_type", sa.Text(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=True),
        sa.Column("option_name", sa.Text(), nullable=False),
        sa.Column("rolled_value", sa.Numeric(), nullable=True),
        sa.Column("max_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_listing_options_listing_id", "listing_options", ["listing_id"])
    op.create_index("ix_listing_options_target", "listing_options", ["option_type", "option_id"])

    # --- Tags ---
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tags_weight", "tags", ["weight"])

    op.create_table(
        "tag_targets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tag_id", "target_type", "target_id", name="_tag_target_uc"),
    )
    op.create_index("ix_tag_targets_target", "tag_targets", ["target_type", "target_id"])
    op.create_index("ix_tag_targets_tag_id", "tag_targets", ["tag_id"])

    # --- OCR Corrections ---
    op.create_table(
        "ocr_corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("line_index", sa.SmallInteger(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("ocr_model", sa.Text(), nullable=True),
        sa.Column("fm_applied", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("charset_mismatch", sa.Text(), nullable=True),
        sa.Column("image_filename", sa.Text(), nullable=False),
        sa.Column("is_stitched", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("trained_version", sa.Text(), nullable=True),
    )
    op.create_index("ix_ocr_corrections_session_id", "ocr_corrections", ["session_id"])

    # --- Job Runs ---
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("ocr_corrections")
    op.drop_table("tag_targets")
    op.drop_table("tags")
    op.drop_table("listing_options")
    op.drop_table("listings")
    op.drop_table("game_items")
    op.drop_table("murias_relic_options")
    op.drop_table("echostone_options")
    op.drop_table("reforge_options")
    op.drop_table("enchant_effects")
    op.drop_table("effects")
    op.drop_table("enchants")
    op.drop_table("role_feature_flags")
    op.drop_table("feature_flags")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
