"""add_index_on_listings_name

Revision ID: 382d0cdad51d
Revises: bc9d9370ad9d
Create Date: 2026-03-06 01:38:37.206252

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '382d0cdad51d'
down_revision: Union[str, Sequence[str], None] = 'bc9d9370ad9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_listings_name', 'listings', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_listings_name', table_name='listings')
