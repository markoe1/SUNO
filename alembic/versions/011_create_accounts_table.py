"""Create accounts table for membership workspace provisioning

Revision ID: 011
Revises: 010
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa


revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('membership_id', sa.Integer, sa.ForeignKey('memberships.id'), nullable=False),
        sa.Column('workspace_id', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'PAUSED', 'REVOKED', 'DISABLED', name='accountstatus', create_type=False), nullable=False),
        sa.Column('automation_enabled', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('accounts')
