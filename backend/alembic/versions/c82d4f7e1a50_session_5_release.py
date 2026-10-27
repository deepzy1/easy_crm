"""Session 5 reviewed ingestion, shared throttling, worker health and privacy audit.

Revision ID: c82d4f7e1a50
Revises: 01e3724d4b96
"""

from alembic import op
import sqlalchemy as sa

revision = "c82d4f7e1a50"
down_revision = "01e3724d4b96"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "channel_inbound_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    for name, length, default in [
        ("kind", 20, "text"),
        ("origin", 500, ""),
        ("state", 30, "ready"),
        ("error", 300, ""),
    ]:
        op.add_column(
            "qualification_knowledge",
            sa.Column(name, sa.String(length), nullable=False, server_default=default),
        )
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.Integer(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"])
    op.create_table(
        "worker_heartbeats",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "privacy_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_privacy_audits_workspace_id", "privacy_audits", ["workspace_id"])


def downgrade():
    op.drop_column("channel_inbound_events", "processed_at")
    op.drop_table("privacy_audits")
    op.drop_table("worker_heartbeats")
    op.drop_table("rate_limit_buckets")
    for name in ("error", "state", "origin", "kind"):
        op.drop_column("qualification_knowledge", name)
