"""Rename campaigns.active to campaigns.available (idempotent)

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
    # Check if 'active' column exists before renaming
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'campaigns' AND column_name = 'active'
        """)
        active_exists = cursor.fetchone() is not None
    except Exception:
        active_exists = False
    finally:
        cursor.close()

    if active_exists:
        # Only rename if 'active' exists
        op.alter_column('campaigns', 'active', new_column_name='available')


def downgrade():
    # Check if 'available' column exists before renaming back
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'campaigns' AND column_name = 'available'
        """)
        available_exists = cursor.fetchone() is not None
    except Exception:
        available_exists = False
    finally:
        cursor.close()

    if available_exists:
        # Only rename if 'available' exists
        op.alter_column('campaigns', 'available', new_column_name='active')
