"""create auth tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('email', sa.Text, nullable=False, unique=True),
        sa.Column('password_hash', sa.Text, nullable=True),
        sa.Column('discord_id', sa.Text, nullable=True, unique=True),
        sa.Column('discord_username', sa.Text, nullable=True),
        sa.Column('server', sa.Text, nullable=True),
        sa.Column('game_id', sa.Text, nullable=True),
        sa.Column('status', sa.SmallInteger, nullable=False, server_default='0'),
        sa.Column('verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('server', 'game_id', name='_user_server_game_id_uc'),
    )

    op.create_table(
        'roles',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.Text, nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.Integer, sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'role_id', name='_user_role_uc'),
    )

    op.create_table(
        'feature_flags',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.Text, nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'role_feature_flags',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('role_id', sa.Integer, sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature_flag_id', sa.Integer, sa.ForeignKey('feature_flags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('role_id', 'feature_flag_id', name='_role_feature_flag_uc'),
    )

    # Seed roles
    roles_table = sa.table('roles', sa.column('name', sa.Text))
    op.bulk_insert(roles_table, [
        {'name': 'master'},
        {'name': 'admin'},
    ])

    # Seed feature flags
    flags_table = sa.table('feature_flags', sa.column('name', sa.Text))
    op.bulk_insert(flags_table, [
        {'name': 'manage_tags'},
        {'name': 'manage_corrections'},
    ])


def downgrade() -> None:
    op.drop_table('role_feature_flags')
    op.drop_table('feature_flags')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('users')
