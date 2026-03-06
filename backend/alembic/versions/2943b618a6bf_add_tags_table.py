"""add_tags_table

Revision ID: 2943b618a6bf
Revises: f5f1995269d9
Create Date: 2026-03-06 00:46:53.612455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2943b618a6bf'
down_revision: Union[str, Sequence[str], None] = 'f5f1995269d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('weight', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_type', 'target_id', 'name', name='_tag_type_id_name_uc'),
    )
    op.create_index('ix_tags_target', 'tags', ['target_type', 'target_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tags_target', table_name='tags')
    op.drop_table('tags')
