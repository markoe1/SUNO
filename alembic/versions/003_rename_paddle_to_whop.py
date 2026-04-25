"""Rename paddle_transaction_id to whop_transaction_id on invoices

Revision ID: 003
Revises: 002
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('invoices') as batch_op:
        batch_op.alter_column(
            'paddle_transaction_id',
            new_column_name='whop_transaction_id',
            existing_type=sa.String(255),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('invoices') as batch_op:
        batch_op.alter_column(
            'whop_transaction_id',
            new_column_name='paddle_transaction_id',
            existing_type=sa.String(255),
            nullable=True,
        )
