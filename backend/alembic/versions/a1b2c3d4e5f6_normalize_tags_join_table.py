"""normalize_tags_join_table

Revision ID: a1b2c3d4e5f6
Revises: bc9d9370ad9d
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '382d0cdad51d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old tags table (truncate approach — no data migration)
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_index('ix_tags_target', table_name='tags')
    op.drop_table('tags')

    # Create normalized tags table (unique tag definitions)
    op.create_table('tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('weight', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='_tag_name_uc'),
    )
    op.create_index('ix_tags_name', 'tags', ['name'], unique=True)
    op.create_index('ix_tags_weight', 'tags', ['weight'], unique=False)

    # Create tag_targets join table
    op.create_table('tag_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tag_id', 'target_type', 'target_id', name='_tag_target_uc'),
    )
    op.create_index('ix_tag_targets_target', 'tag_targets', ['target_type', 'target_id'], unique=False)
    op.create_index('ix_tag_targets_tag_id', 'tag_targets', ['tag_id'], unique=False)


def downgrade() -> None:
    # Drop normalized tables
    op.drop_index('ix_tag_targets_tag_id', table_name='tag_targets')
    op.drop_index('ix_tag_targets_target', table_name='tag_targets')
    op.drop_table('tag_targets')

    op.drop_index('ix_tags_weight', table_name='tags')
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_table('tags')

    # Recreate old denormalized tags table
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
    op.create_index('ix_tags_name', 'tags', ['name'], unique=False)
