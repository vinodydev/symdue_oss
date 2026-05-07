# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""Add node name column

Revision ID: add_node_name_001
Revises: 709e3eae2157
Create Date: 2026-02-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_node_name_001'
down_revision = '709e3eae2157'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add name column as nullable
    op.add_column('workflow_nodes', sa.Column('name', sa.String(length=255), nullable=True))
    
    # Step 2: Generate default names for existing nodes
    # Format: "node_{node_type_id}_{short_uuid}" (e.g., "node_custom-python_a1b2c3")
    op.execute(text("""
        UPDATE workflow_nodes
        SET name = 'node_' || node_type_id || '_' || SUBSTRING(id::text, 1, 8)
        WHERE name IS NULL
    """))
    
    # Step 3: Make name NOT NULL
    op.alter_column('workflow_nodes', 'name', nullable=False)
    
    # Step 4: Add unique constraint on (workflow_id, name) for non-deleted nodes
    # We use a partial unique index since we only care about uniqueness for active nodes
    op.create_index(
        'ix_workflow_nodes_workflow_id_name_unique',
        'workflow_nodes',
        ['workflow_id', 'name'],
        unique=True,
        postgresql_where=text('deleted_at IS NULL')
    )


def downgrade() -> None:
    # Remove unique index
    op.drop_index('ix_workflow_nodes_workflow_id_name_unique', table_name='workflow_nodes')
    
    # Remove name column
    op.drop_column('workflow_nodes', 'name')

