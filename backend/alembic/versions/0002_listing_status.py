"""add status column to listings

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default 0 (draft) for future inserts; existing rows get 1 (listed)
    op.add_column(
        "listings",
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE listings SET status = 1")
    op.create_index("ix_listings_status", "listings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_listings_status", table_name="listings")
    op.drop_column("listings", "status")
