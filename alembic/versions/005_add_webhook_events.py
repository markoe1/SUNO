"""Add webhook_events table for Whop webhook lifecycle tracking.

Revision ID: 005_add_webhook_events
Revises: 004_add_whop_membership_id
Create Date: 2026-04-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_add_webhook_events"
down_revision = "004_add_whop_membership_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create webhook_events table for storing and tracking Whop webhook events."""
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("whop_event_id", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("job_id", sa.String(255), nullable=True, index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processing_result", postgresql.JSON, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for efficient querying
    op.create_index("idx_webhook_event_id", "webhook_events", ["whop_event_id"])
    op.create_index("idx_webhook_status", "webhook_events", ["status"])
    op.create_index("idx_webhook_job_id", "webhook_events", ["job_id"])


def downgrade() -> None:
    """Drop webhook_events table (only for local development, never in production)."""
    op.drop_index("idx_webhook_job_id", table_name="webhook_events")
    op.drop_index("idx_webhook_status", table_name="webhook_events")
    op.drop_index("idx_webhook_event_id", table_name="webhook_events")
    op.drop_table("webhook_events")
