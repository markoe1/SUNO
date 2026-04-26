"""Create PostgreSQL ENUM type for TierName

Revision ID: 010
Revises: 009
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa


revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Create the tiername ENUM type in PostgreSQL
    tier_enum = sa.Enum('STARTER', 'PRO', name='tiername')
    tier_enum.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Drop the tiername ENUM type
    tier_enum = sa.Enum('STARTER', 'PRO', name='tiername')
    tier_enum.drop(op.get_bind(), checkfirst=True)
