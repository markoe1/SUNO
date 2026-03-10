"""Add client management tables

Revision ID: 002
Revises: 001
Create Date: 2024-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create clients table
    op.create_table('clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(320), nullable=True),
        sa.Column('niche', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('LEAD', 'TRIAL', 'ACTIVE', 'PAUSED', 'CHURNED', name='clientstatus'), nullable=False),
        sa.Column('monthly_rate', sa.Float(), nullable=False),
        sa.Column('view_guarantee', sa.Integer(), nullable=False),
        sa.Column('clips_per_month', sa.Integer(), nullable=False),
        sa.Column('tiktok_username', sa.String(100), nullable=True),
        sa.Column('instagram_username', sa.String(100), nullable=True),
        sa.Column('youtube_channel', sa.String(255), nullable=True),
        sa.Column('drive_folder', sa.Text(), nullable=True),
        sa.Column('content_notes', sa.Text(), nullable=True),
        sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('churned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clients_user_id'), 'clients', ['user_id'], unique=False)
    
    # Create editors table
    op.create_table('editors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(320), nullable=True),
        sa.Column('rate_per_clip', sa.Float(), nullable=False),
        sa.Column('total_clips_edited', sa.Integer(), nullable=False),
        sa.Column('avg_turnaround_hours', sa.Float(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_editors_user_id'), 'editors', ['user_id'], unique=False)
    
    # Create client_clips table
    op.create_table('client_clips',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('editor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('raw_file_path', sa.Text(), nullable=True),
        sa.Column('edited_file_path', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('RAW', 'EDITING', 'REVIEW', 'APPROVED', 'POSTED', 'REJECTED', name='clipstatus'), nullable=False),
        sa.Column('tiktok_url', sa.Text(), nullable=True),
        sa.Column('instagram_url', sa.Text(), nullable=True),
        sa.Column('youtube_url', sa.Text(), nullable=True),
        sa.Column('total_views', sa.Integer(), nullable=False),
        sa.Column('total_likes', sa.Integer(), nullable=False),
        sa.Column('total_comments', sa.Integer(), nullable=False),
        sa.Column('total_shares', sa.Integer(), nullable=False),
        sa.Column('hook_used', sa.Text(), nullable=True),
        sa.Column('hashtags', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['editor_id'], ['editors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_client_clips_client_id'), 'client_clips', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_clips_editor_id'), 'client_clips', ['editor_id'], unique=False)
    
    # Create invoices table
    op.create_table('invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.String(7), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('base_amount', sa.Float(), nullable=False),
        sa.Column('performance_bonus', sa.Float(), nullable=False),
        sa.Column('clips_delivered', sa.Integer(), nullable=False),
        sa.Column('total_views', sa.Integer(), nullable=False),
        sa.Column('view_guarantee_met', sa.Boolean(), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(255), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoices_client_id'), 'invoices', ['client_id'], unique=False)
    
    # Create performance_reports table
    op.create_table('performance_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_clips', sa.Integer(), nullable=False),
        sa.Column('total_views', sa.Integer(), nullable=False),
        sa.Column('total_likes', sa.Integer(), nullable=False),
        sa.Column('total_comments', sa.Integer(), nullable=False),
        sa.Column('total_shares', sa.Integer(), nullable=False),
        sa.Column('top_clips_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('best_hooks_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('insights_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_reports_client_id'), 'performance_reports', ['client_id'], unique=False)
    
    # Create clip_templates table
    op.create_table('clip_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('niche', sa.String(100), nullable=True),
        sa.Column('hook_text', sa.Text(), nullable=False),
        sa.Column('structure_notes', sa.Text(), nullable=True),
        sa.Column('times_used', sa.Integer(), nullable=False),
        sa.Column('avg_views', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clip_templates_user_id'), 'clip_templates', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_clip_templates_user_id'), table_name='clip_templates')
    op.drop_table('clip_templates')
    op.drop_index(op.f('ix_performance_reports_client_id'), table_name='performance_reports')
    op.drop_table('performance_reports')
    op.drop_index(op.f('ix_invoices_client_id'), table_name='invoices')
    op.drop_table('invoices')
    op.drop_index(op.f('ix_client_clips_editor_id'), table_name='client_clips')
    op.drop_index(op.f('ix_client_clips_client_id'), table_name='client_clips')
    op.drop_table('client_clips')
    op.drop_index(op.f('ix_editors_user_id'), table_name='editors')
    op.drop_table('editors')
    op.drop_index(op.f('ix_clients_user_id'), table_name='clients')
    op.drop_table('clients')
    op.execute('DROP TYPE IF EXISTS clientstatus')
    op.execute('DROP TYPE IF EXISTS clipstatus')