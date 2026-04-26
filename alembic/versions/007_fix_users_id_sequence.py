"""Fix users.id to use SERIAL/autoincrement for Integer primary key

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
    # Create sequence for users.id (PostgreSQL SERIAL equivalent)
    op.execute("CREATE SEQUENCE users_id_seq START 1")

    # Alter users.id to use the sequence with proper defaults
    op.alter_column(
        'users',
        'id',
        existing_type=sa.Integer,
        server_default=sa.text("nextval('users_id_seq'::regclass)"),
        existing_nullable=False
    )


def downgrade():
    # Remove the default
    op.alter_column(
        'users',
        'id',
        existing_type=sa.Integer,
        server_default=None,
        existing_nullable=False
    )

    # Drop sequence
    op.execute("DROP SEQUENCE users_id_seq")
