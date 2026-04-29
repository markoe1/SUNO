"""Rename campaigns.active to campaigns.available

Revision ID: 014
Revises: 013
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa


revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    # Rename 'active' column to 'available' in campaigns table
    op.alter_column('campaigns', 'active', new_column_name='available')


def downgrade():
    # Rename 'available' column back to 'active' in campaigns table
    op.alter_column('campaigns', 'available', new_column_name='active')
