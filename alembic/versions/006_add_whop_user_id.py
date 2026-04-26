"""Add whop_user_id to users table

Revision ID: 006
Revises: 005
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('whop_user_id', sa.String(255), nullable=True, unique=True)
    )
    op.create_index('idx_users_whop_user_id', 'users', ['whop_user_id'])


def downgrade():
    op.drop_index('idx_users_whop_user_id', table_name='users')
    op.drop_column('users', 'whop_user_id')
