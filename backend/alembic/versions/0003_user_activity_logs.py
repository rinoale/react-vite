"""add user_activity_logs table

Revision ID: 0003
Revises: 6800a1f43787
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0003"
down_revision = "6800a1f43787"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_user_id", "user_activity_logs", ["user_id"])
    op.create_index("ix_activity_action", "user_activity_logs", ["action"])
    op.create_index("ix_activity_target", "user_activity_logs", ["target_type", "target_id"])
    op.create_index("ix_activity_created_at", "user_activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("user_activity_logs")
