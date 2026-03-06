"""add_listing_description

Revision ID: 0bf318d9537f
Revises: 2943b618a6bf
Create Date: 2026-03-06 00:57:43.918658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bf318d9537f'
down_revision: Union[str, Sequence[str], None] = '2943b618a6bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'description')
