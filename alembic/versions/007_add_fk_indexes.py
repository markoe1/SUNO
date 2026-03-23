"""Add indexes on high-traffic FK columns.

Revision ID: 007
Revises: 006
Create Date: 2026-03-23

Adds indexes that were missing on every FK column used in WHERE clauses:
  clients.user_id         — every operator dashboard query filters on this
  editors.user_id         — operator editor list
  client_clips.client_id  — clip pipeline queries
  client_clips.editor_id  — editor portal clips query
  invoices.client_id      — invoice listing + portal
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_clients_user_id", "clients", ["user_id"])
    op.create_index("ix_editors_user_id", "editors", ["user_id"])
    op.create_index("ix_editors_email", "editors", ["email"])
    op.create_index("ix_client_clips_client_id", "client_clips", ["client_id"])
    op.create_index("ix_client_clips_editor_id", "client_clips", ["editor_id"])
    op.create_index("ix_invoices_client_id", "invoices", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_clients_user_id", "clients")
    op.drop_index("ix_editors_user_id", "editors")
    op.drop_index("ix_editors_email", "editors")
    op.drop_index("ix_client_clips_client_id", "client_clips")
    op.drop_index("ix_client_clips_editor_id", "client_clips")
    op.drop_index("ix_invoices_client_id", "invoices")
