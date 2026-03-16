"""Add whop_membership_id to users

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('whop_membership_id', sa.String(255), nullable=True)
    )
    op.create_index('ix_users_whop_membership_id', 'users', ['whop_membership_id'])


def downgrade():
    op.drop_index('ix_users_whop_membership_id', table_name='users')
    op.drop_column('users', 'whop_membership_id')
