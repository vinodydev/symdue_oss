"""Add workflow_waits, events, and event_invocations tables

Revision ID: add_wait_signal_event_001
Revises: add_source_handle_001
Create Date: 2026-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_wait_signal_event_001"
down_revision = "add_execution_config_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── workflow_waits ──────────────────────────────────────────────────────
    op.create_table(
        "workflow_waits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="signal"),
        sa.Column("signals_needed", sa.JSON(), nullable=True),
        sa.Column("signals_received", sa.JSON(), nullable=True),
        sa.Column("timeout_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("satisfied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("satisfied_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["run_history.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "node_id", name="uq_workflow_wait_run_node"),
    )
    op.create_index("ix_workflow_waits_channel", "workflow_waits", ["channel"])

    # ── events ─────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("schedule", sa.String(), nullable=True),
        sa.Column("script", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("queue_name", sa.String(), nullable=True),
        sa.Column("webhook_secret", sa.String(), nullable=True),
        sa.Column("last_run_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("next_run_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── event_invocations ──────────────────────────────────────────────────
    op.create_table(
        "event_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("state_before", sa.JSON(), nullable=True),
        sa.Column("state_after", sa.JSON(), nullable=True),
        sa.Column("log_output", sa.Text(), nullable=True),
        sa.Column("runtime_calls", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_invocations_event_id", "event_invocations", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_invocations_event_id", table_name="event_invocations")
    op.drop_table("event_invocations")
    op.drop_table("events")
    op.drop_index("ix_workflow_waits_channel", table_name="workflow_waits")
    op.drop_table("workflow_waits")
