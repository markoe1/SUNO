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
    # Create accountstatus ENUM type if it doesn't exist
    accountstatus_enum = sa.Enum('ACTIVE', 'PAUSED', 'REVOKED', 'DISABLED', name='accountstatus')
    accountstatus_enum.create(op.get_bind(), checkfirst=True)

    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('membership_id', sa.Integer, sa.ForeignKey('memberships.id'), nullable=False, unique=True, index=True),
        sa.Column('workspace_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('status', accountstatus_enum, nullable=False, server_default='ACTIVE'),
        sa.Column('automation_enabled', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create index for workspace_id
    op.create_index('idx_account_workspace', 'accounts', ['workspace_id'])


def downgrade():
    # Drop indexes and table
    op.drop_index('idx_account_workspace', table_name='accounts')
    op.drop_table('accounts')

    # Drop accountstatus ENUM type
    accountstatus_enum = sa.Enum('ACTIVE', 'PAUSED', 'REVOKED', 'DISABLED', name='accountstatus')
    accountstatus_enum.drop(op.get_bind(), checkfirst=True)
