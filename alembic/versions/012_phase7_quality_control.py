"""Phase 7 — Quality Control Foundation + Vantage Architecture

Revision ID: 012
Revises: 011
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa


revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Add new ClipLifecycle enum values (safe, irreversible)
    op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'generated'")
    op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'needs_review'")
    op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'approved'")
    op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'rejected'")

    # Create creator_profiles table
    op.create_table(
        'creator_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('account_id', sa.Integer, sa.ForeignKey('accounts.id'), nullable=False, unique=True),
        sa.Column('niche', sa.String(255), nullable=True),
        sa.Column('tone', sa.String(100), nullable=True),
        sa.Column('content_style', sa.String(100), nullable=True),
        sa.Column('hook_style', sa.String(100), nullable=True),
        sa.Column('avg_clip_length', sa.Integer, nullable=True),
        sa.Column('do_not_use', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('platform_focus', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('winning_clip_ids', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_creator_profile_account', 'creator_profiles', ['account_id'])

    # Add columns to campaigns table
    op.add_column('campaigns', sa.Column('min_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('max_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('ideal_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('audience', sa.String(255), nullable=True))
    op.add_column('campaigns', sa.Column('cta', sa.Text, nullable=True))
    op.add_column('campaigns', sa.Column('forbidden_topics', sa.JSON, nullable=False, server_default='[]'))
    op.add_column('campaigns', sa.Column('approval_required', sa.Boolean, nullable=False, server_default='false'))

    # Add quality score columns to clips table
    op.add_column('clips', sa.Column('hook_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('relevance_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('platform_fit_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('duration_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('brand_alignment_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('viral_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('social_proof_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('overall_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('monetization_score', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('emotional_trigger_type', sa.String(50), nullable=True))
    op.add_column('clips', sa.Column('rejection_reason', sa.Text, nullable=True))
    op.add_column('clips', sa.Column('hook_start_ms', sa.Integer, nullable=True))

    # Add index to clips for account_id, status
    op.create_index('idx_clip_account_status', 'clips', ['account_id', 'status'])


def downgrade():
    # Drop index
    op.drop_index('idx_clip_account_status', 'clips')

    # Drop quality score columns from clips
    op.drop_column('clips', 'hook_score')
    op.drop_column('clips', 'relevance_score')
    op.drop_column('clips', 'platform_fit_score')
    op.drop_column('clips', 'duration_score')
    op.drop_column('clips', 'brand_alignment_score')
    op.drop_column('clips', 'viral_score')
    op.drop_column('clips', 'social_proof_score')
    op.drop_column('clips', 'overall_score')
    op.drop_column('clips', 'monetization_score')
    op.drop_column('clips', 'emotional_trigger_type')
    op.drop_column('clips', 'rejection_reason')
    op.drop_column('clips', 'hook_start_ms')

    # Drop columns from campaigns
    op.drop_column('campaigns', 'min_duration_seconds')
    op.drop_column('campaigns', 'max_duration_seconds')
    op.drop_column('campaigns', 'ideal_duration_seconds')
    op.drop_column('campaigns', 'audience')
    op.drop_column('campaigns', 'cta')
    op.drop_column('campaigns', 'forbidden_topics')
    op.drop_column('campaigns', 'approval_required')

    # Drop creator_profiles table
    op.drop_index('idx_creator_profile_account', 'creator_profiles')
    op.drop_table('creator_profiles')
