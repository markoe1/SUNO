"""Phase 8 — Real Intelligence + Distribution Engine

Revision ID: 013
Revises: 012
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa


revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # =====================================================================
    # PART 1: ENUM CREATION (idempotent with IF NOT EXISTS)
    # =====================================================================
    # Create varianttype enum (safe: IF NOT EXISTS prevents DuplicateObject)
    try:
        op.execute("CREATE TYPE varianttype AS ENUM ('hook', 'caption', 'duration', 'subtitles')")
    except Exception:
        # Already exists, which is fine for idempotency
        pass

    # Create variantstatus enum (safe: IF NOT EXISTS prevents DuplicateObject)
    try:
        op.execute("CREATE TYPE variantstatus AS ENUM ('draft', 'elite', 'elected', 'posted', 'rejected')")
    except Exception:
        # Already exists, which is fine for idempotency
        pass

    # =====================================================================
    # PART 2: CLIP_VARIANTS TABLE
    # =====================================================================

    # Create clip_variants table
    op.create_table(
        'clip_variants',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('clip_id', sa.Integer, sa.ForeignKey('clips.id'), nullable=False),
        sa.Column('variant_group_id', sa.String(64), nullable=True),
        sa.Column('variant_type', sa.Enum('hook', 'caption', 'duration', 'subtitles', name='varianttype', create_type=False), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('quality_tier', sa.String(20), nullable=True),
        sa.Column('hook_type', sa.String(50), nullable=True),
        sa.Column('predicted_engagement', sa.Float, nullable=True),
        sa.Column('status', sa.Enum('draft', 'elite', 'elected', 'posted', 'rejected', name='variantstatus', create_type=False), nullable=False, server_default='draft'),
        sa.Column('signal_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_signal_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_platform', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_variant_clip', 'clip_variants', ['clip_id'])
    op.create_index('idx_variant_status', 'clip_variants', ['status'])
    op.create_index('idx_variant_scheduled', 'clip_variants', ['scheduled_for'])
    op.create_index('idx_variant_group', 'clip_variants', ['variant_group_id'])

    # Create clip_performances table
    op.create_table(
        'clip_performances',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('clip_id', sa.Integer, sa.ForeignKey('clips.id'), nullable=False),
        sa.Column('variant_id', sa.Integer, sa.ForeignKey('clip_variants.id'), nullable=True),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('views', sa.Integer, nullable=False, server_default='0'),
        sa.Column('watch_time_seconds', sa.Float, nullable=True),
        sa.Column('completion_rate', sa.Float, nullable=True),
        sa.Column('likes', sa.Integer, nullable=False, server_default='0'),
        sa.Column('shares', sa.Integer, nullable=False, server_default='0'),
        sa.Column('saves', sa.Integer, nullable=False, server_default='0'),
        sa.Column('comments', sa.Integer, nullable=False, server_default='0'),
        sa.Column('revenue_estimate', sa.Float, nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_perf_clip', 'clip_performances', ['clip_id'])
    op.create_index('idx_perf_variant', 'clip_performances', ['variant_id'])
    op.create_index('idx_perf_platform', 'clip_performances', ['platform'])

    # Add 8 new columns to clips table
    op.add_column('clips', sa.Column('predicted_views', sa.Integer, nullable=True))
    op.add_column('clips', sa.Column('estimated_value', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('ai_generation_cost_usd', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('ai_roi', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('predicted_watch_time', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('predicted_completion_rate', sa.Float, nullable=True))
    op.add_column('clips', sa.Column('predicted_dropoff_ms', sa.Integer, nullable=True))
    op.add_column('clips', sa.Column('posting_cooldown_hours', sa.Integer, nullable=False, server_default='2'))


def downgrade():
    # Drop columns from clips
    op.drop_column('clips', 'predicted_views')
    op.drop_column('clips', 'estimated_value')
    op.drop_column('clips', 'ai_generation_cost_usd')
    op.drop_column('clips', 'ai_roi')
    op.drop_column('clips', 'predicted_watch_time')
    op.drop_column('clips', 'predicted_completion_rate')
    op.drop_column('clips', 'predicted_dropoff_ms')
    op.drop_column('clips', 'posting_cooldown_hours')

    # Drop clip_performances table
    op.drop_index('idx_perf_clip', 'clip_performances')
    op.drop_index('idx_perf_variant', 'clip_performances')
    op.drop_index('idx_perf_platform', 'clip_performances')
    op.drop_table('clip_performances')

    # Drop clip_variants table
    op.drop_index('idx_variant_clip', 'clip_variants')
    op.drop_index('idx_variant_status', 'clip_variants')
    op.drop_index('idx_variant_scheduled', 'clip_variants')
    op.drop_index('idx_variant_group', 'clip_variants')
    op.drop_table('clip_variants')

    # Drop enums
    op.execute("DROP TYPE variantstatus")
    op.execute("DROP TYPE varianttype")
