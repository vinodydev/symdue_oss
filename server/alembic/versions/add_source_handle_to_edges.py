"""Add source_handle to workflow_edges for condition node branches

Revision ID: add_source_handle_001
Revises: add_node_type_system
Create Date: 2026-03-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "add_source_handle_001"
down_revision = "add_node_type_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_edges",
        sa.Column("source_handle", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_edges", "source_handle")
