# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""Add storage system tables

Revision ID: add_storage_system
Revises: add_node_name_001
Create Date: 2026-02-14 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_storage_system'
down_revision = 'add_node_name_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create storage_configs table
    op.create_table(
        'storage_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('storage_type', sa.String(50), nullable=False),
        sa.Column('config', postgresql.JSONB, nullable=False),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    op.create_index('ix_storage_configs_name', 'storage_configs', ['name'], unique=True)
    
    # Note: Storage references are stored in node.config["storages"] JSON
    # No separate association table needed!


def downgrade():
    op.drop_index('ix_storage_configs_name', table_name='storage_configs')
    op.drop_table('storage_configs')

