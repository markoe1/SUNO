"""Make password_hash nullable for Whop-created users without passwords

Revision ID: 007
Revises: 006
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Allow password_hash to be NULL for Whop-created users (no password authentication)
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.Text,
        nullable=True,
        existing_nullable=False
    )


def downgrade():
    # Restore NOT NULL constraint (only for development)
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.Text,
        nullable=False,
        existing_nullable=True
    )
