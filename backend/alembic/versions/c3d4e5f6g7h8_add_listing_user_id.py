"""add user_id to listings

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_listings_user_id', 'listings', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_listings_user_id', table_name='listings')
    op.drop_column('listings', 'user_id')
