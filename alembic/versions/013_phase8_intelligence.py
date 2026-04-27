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
    # PART 1: ENUM CREATION (idempotent with PostgreSQL DO blocks)
    # =====================================================================
    # Create varianttype enum if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'varianttype'
                  AND n.nspname = 'public'
            ) THEN
                CREATE TYPE varianttype AS ENUM ('hook', 'caption', 'duration', 'subtitles');
            END IF;
        END $$;
    """)

    # Create variantstatus enum if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'variantstatus'
                  AND n.nspname = 'public'
            ) THEN
                CREATE TYPE variantstatus AS ENUM ('draft', 'elite', 'elected', 'posted', 'rejected');
            END IF;
        END $$;
    """)

    # =====================================================================
    # PART 2: CLIP_VARIANTS TABLE (raw SQL to avoid enum conflicts)
    # =====================================================================
    # Check if clip_variants table exists
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'clip_variants'
        """)
        clip_variants_exists = cursor.fetchone() is not None
    except Exception:
        clip_variants_exists = False

    cursor.close()

    if not clip_variants_exists:
        # Create clip_variants table with all columns (fresh database)
        op.execute("""
            CREATE TABLE clip_variants (
                id SERIAL PRIMARY KEY,
                clip_id INTEGER NOT NULL REFERENCES clips(id),
                variant_group_id VARCHAR(64),
                variant_type varianttype NOT NULL,
                content TEXT NOT NULL,
                model_used VARCHAR(100),
                quality_tier VARCHAR(20),
                hook_type VARCHAR(50),
                predicted_engagement REAL,
                status variantstatus NOT NULL DEFAULT 'draft',
                signal_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                scheduled_for TIMESTAMP WITH TIME ZONE,
                first_signal_at TIMESTAMP WITH TIME ZONE,
                posted_at TIMESTAMP WITH TIME ZONE,
                posted_platform VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        # Create indexes
        op.execute("CREATE INDEX idx_variant_clip ON clip_variants(clip_id)")
        op.execute("CREATE INDEX idx_variant_status ON clip_variants(status)")
        op.execute("CREATE INDEX idx_variant_scheduled ON clip_variants(scheduled_for)")
        op.execute("CREATE INDEX idx_variant_group ON clip_variants(variant_group_id)")

    # =====================================================================
    # PART 3: CLIP_PERFORMANCES TABLE (raw SQL for consistency)
    # =====================================================================
    # Check if clip_performances table exists
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'clip_performances'
        """)
        clip_performances_exists = cursor.fetchone() is not None
    except Exception:
        clip_performances_exists = False

    cursor.close()

    if not clip_performances_exists:
        # Create clip_performances table with all columns (fresh database)
        op.execute("""
            CREATE TABLE clip_performances (
                id SERIAL PRIMARY KEY,
                clip_id INTEGER NOT NULL REFERENCES clips(id),
                variant_id INTEGER REFERENCES clip_variants(id),
                platform VARCHAR(50) NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                watch_time_seconds REAL,
                completion_rate REAL,
                likes INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                saves INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                revenue_estimate REAL,
                recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        # Create indexes
        op.execute("CREATE INDEX idx_perf_clip ON clip_performances(clip_id)")
        op.execute("CREATE INDEX idx_perf_variant ON clip_performances(variant_id)")
        op.execute("CREATE INDEX idx_perf_platform ON clip_performances(platform)")

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
