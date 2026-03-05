"""add_index_on_tags_name

Revision ID: bc9d9370ad9d
Revises: 0bf318d9537f
Create Date: 2026-03-06 01:23:26.693098

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bc9d9370ad9d'
down_revision: Union[str, Sequence[str], None] = '0bf318d9537f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_tags_name', 'tags', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_tags_name', table_name='tags')
