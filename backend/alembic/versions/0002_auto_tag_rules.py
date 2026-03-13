"""auto_tag_rules table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_tag_rules",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_auto_tag_rules_enabled_priority",
        "auto_tag_rules",
        ["enabled", "priority"],
    )


def downgrade() -> None:
    op.drop_table("auto_tag_rules")
