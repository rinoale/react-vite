"""add payload column to job_runs

Revision ID: 6800a1f43787
Revises: 0002
Create Date: 2026-03-10 17:26:01.197602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6800a1f43787'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_runs', sa.Column('payload', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_runs', 'payload')
