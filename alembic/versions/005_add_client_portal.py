"""Add client portal tokens table

Revision ID: 005
Revises: 004
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'client_portal_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_portal_tokens_token_hash', 'client_portal_tokens', ['token_hash'], unique=True)
    op.create_index('ix_client_portal_tokens_client_id', 'client_portal_tokens', ['client_id'])


def downgrade():
    op.drop_index('ix_client_portal_tokens_client_id', table_name='client_portal_tokens')
    op.drop_index('ix_client_portal_tokens_token_hash', table_name='client_portal_tokens')
    op.drop_table('client_portal_tokens')
