"""Phase 7 — Quality Control Foundation + Vantage Architecture

Revision ID: 012
Revises: 011
Create Date: 2026-04-26

CRITICAL: Uses raw SQL for clips table to avoid SQLAlchemy enum auto-creation conflicts.
"""
from alembic import op
import sqlalchemy as sa


revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # =====================================================================
    # PART 1: ENUM CREATION (manual control, no SQLAlchemy interference)
    # =====================================================================
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM pg_type
            WHERE typname = 'cliplifecycle' AND typtype = 'e'
        """)
        enum_exists = cursor.fetchone() is not None
    except Exception:
        enum_exists = False

    cursor.close()

    if not enum_exists:
        # Fresh database: create cliplifecycle enum
        op.execute("""
            CREATE TYPE cliplifecycle AS ENUM (
                'discovered', 'eligible', 'queued', 'generated', 'needs_review',
                'approved', 'captioned', 'scheduled', 'posted', 'submitted',
                'tracked', 'rejected', 'failed', 'expired'
            )
        """)
    else:
        # Legacy database: add new values if missing
        op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'generated'")
        op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'needs_review'")
        op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'approved'")
        op.execute("ALTER TYPE cliplifecycle ADD VALUE IF NOT EXISTS 'rejected'")

    # =====================================================================
    # PART 2: CREATOR_PROFILES TABLE (SQLAlchemy safe, no enum conflicts)
    # =====================================================================
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

    # =====================================================================
    # PART 3: CAMPAIGNS TABLE COLUMNS (legacy database safe)
    # =====================================================================
    op.add_column('campaigns', sa.Column('min_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('max_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('ideal_duration_seconds', sa.Integer, nullable=True))
    op.add_column('campaigns', sa.Column('audience', sa.String(255), nullable=True))
    op.add_column('campaigns', sa.Column('cta', sa.Text, nullable=True))
    op.add_column('campaigns', sa.Column('forbidden_topics', sa.JSON, nullable=False, server_default='[]'))
    op.add_column('campaigns', sa.Column('approval_required', sa.Boolean, nullable=False, server_default='false'))

    # =====================================================================
    # PART 2: CLIPS TABLE (raw SQL to avoid SQLAlchemy enum conflicts)
    # =====================================================================
    conn = op.get_bind()
    cursor = conn.connection.cursor()

    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'clips'
        """)
        clips_exists = cursor.fetchone() is not None
    except Exception:
        clips_exists = False

    cursor.close()

    if not clips_exists:
        # Create clips table with all columns at once (fresh database)
        # Using raw SQL to avoid SQLAlchemy enum auto-creation conflicts
        op.execute("""
            CREATE TABLE clips (
                id SERIAL PRIMARY KEY,
                campaign_id UUID NOT NULL REFERENCES campaigns(id),
                account_id INTEGER REFERENCES accounts(id),
                source_url VARCHAR(2000) NOT NULL UNIQUE,
                source_platform VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                creator VARCHAR(255),
                view_count INTEGER NOT NULL DEFAULT 0,
                engagement_score REAL NOT NULL DEFAULT 0.0,
                trending_category VARCHAR(100),
                hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
                audio_source VARCHAR(255),
                content_hash VARCHAR(64) NOT NULL UNIQUE,
                status cliplifecycle NOT NULL,
                platform_eligible BOOLEAN NOT NULL DEFAULT true,
                available BOOLEAN NOT NULL DEFAULT true,
                clip_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                hook_score REAL,
                relevance_score REAL,
                platform_fit_score REAL,
                duration_score REAL,
                brand_alignment_score REAL,
                viral_score REAL,
                social_proof_score REAL,
                overall_score REAL,
                monetization_score REAL,
                emotional_trigger_type VARCHAR(50),
                rejection_reason TEXT,
                hook_start_ms INTEGER
            )
        """)
        # Create indexes for fresh database
        op.execute("CREATE INDEX idx_clip_campaign ON clips(campaign_id)")
        op.execute("CREATE INDEX idx_clip_account ON clips(account_id)")
        op.execute("CREATE INDEX idx_clip_source_url ON clips(source_url)")
        op.execute("CREATE INDEX idx_clip_content_hash ON clips(content_hash)")
        op.execute("CREATE INDEX idx_clip_status ON clips(status)")
        op.execute("CREATE INDEX idx_clip_account_status ON clips(account_id, status)")
    else:
        # Table exists, add columns if they don't exist
        # Check and add each column individually to avoid duplicate column errors
        conn = op.get_bind()
        cursor = conn.connection.cursor()

        columns_to_add = [
            ('hook_score', 'REAL'),
            ('relevance_score', 'REAL'),
            ('platform_fit_score', 'REAL'),
            ('duration_score', 'REAL'),
            ('brand_alignment_score', 'REAL'),
            ('viral_score', 'REAL'),
            ('social_proof_score', 'REAL'),
            ('overall_score', 'REAL'),
            ('monetization_score', 'REAL'),
            ('emotional_trigger_type', 'VARCHAR(50)'),
            ('rejection_reason', 'TEXT'),
            ('hook_start_ms', 'INTEGER'),
        ]

        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'clips' AND column_name = '{col_name}'
                """)
                column_exists = cursor.fetchone() is not None
            except Exception:
                column_exists = False

            if not column_exists:
                op.execute(f"ALTER TABLE clips ADD COLUMN {col_name} {col_type}")

        cursor.close()

        # Create idx_clip_account_status if it doesn't exist
        try:
            cursor = conn.connection.cursor()
            cursor.execute("""
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_clip_account_status'
            """)
            index_exists = cursor.fetchone() is not None
            cursor.close()
        except Exception:
            index_exists = False

        if not index_exists:
            op.execute("CREATE INDEX idx_clip_account_status ON clips(account_id, status)")


def downgrade():
    # Drop index
    op.drop_index('idx_clip_account_status', 'clips')

    # Note: Do NOT drop cliplifecycle enum in downgrade
    # It may be in use by other tables or have been created elsewhere
    # The enum will be cleaned up by comprehensive cleanup if needed

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
