"""Ensure tiers and memberships tables exist (safe idempotent migration)

Revision ID: 009
Revises: 008
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Get current connection to check for existing tables
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # Create tiers table if it doesn't exist
    if 'tiers' not in existing_tables:
        op.create_table(
            'tiers',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(50), nullable=False, unique=True),
            sa.Column('max_daily_clips', sa.Integer, nullable=False),
            sa.Column('max_platforms', sa.Integer, nullable=False),
            sa.Column('platforms', postgresql.JSON, nullable=False),
            sa.Column('auto_posting', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('scheduling', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('analytics', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('api_access', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # Create memberships table if it doesn't exist
    if 'memberships' not in existing_tables:
        op.create_table(
            'memberships',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
            sa.Column('tier_id', sa.Integer, sa.ForeignKey('tiers.id'), nullable=False),
            sa.Column('whop_membership_id', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('whop_plan_id', sa.String(255), nullable=True, index=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('clips_today_count', sa.Integer, nullable=False, server_default='0'),
        )

        # Create indexes for memberships
        op.create_index('idx_membership_user', 'memberships', ['user_id'])
        op.create_index('idx_membership_whop_id', 'memberships', ['whop_membership_id'])
        op.create_unique_constraint('uq_user_whop_membership', 'memberships', ['user_id', 'whop_membership_id'])


def downgrade():
    # Remove memberships table
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    if 'memberships' in existing_tables:
        op.drop_constraint('uq_user_whop_membership', 'memberships')
        op.drop_index('idx_membership_whop_id', table_name='memberships')
        op.drop_index('idx_membership_user', table_name='memberships')
        op.drop_table('memberships')

    # Remove tiers table
    if 'tiers' in existing_tables:
        op.drop_table('tiers')
