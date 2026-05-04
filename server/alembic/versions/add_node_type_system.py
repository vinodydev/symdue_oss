"""Add node type system extensions

Revision ID: add_node_type_system
Revises: add_default_minio_001
Create Date: 2026-02-15 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_node_type_system'
down_revision = 'add_default_minio_001'
branch_labels = None
depends_on = None


def upgrade():
    # Extend node_types table
    op.add_column('node_types', sa.Column('type_kind', sa.String(length=50), nullable=True))
    op.add_column('node_types', sa.Column('node_template_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('workflow_template_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('node_types', sa.Column('workflow_env_template', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('node_env_template', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('input_ports', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('output_ports', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('node_types', sa.Column('version', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('node_types', sa.Column('parent_template_id', sa.String(length=255), nullable=True))
    op.add_column('node_types', sa.Column('is_public', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('node_types', sa.Column('usage_count', sa.Integer(), nullable=True, server_default='0'))
    
    # Add foreign key for workflow_id
    op.create_foreign_key(
        'fk_node_types_workflow_id',
        'node_types', 'workflows',
        ['workflow_id'], ['id']
    )
    
    # Add foreign key for parent_template_id
    op.create_foreign_key(
        'fk_node_types_parent_template_id',
        'node_types', 'node_types',
        ['parent_template_id'], ['id']
    )
    
    # Set default type_kind for existing records
    op.execute(text("UPDATE node_types SET type_kind = 'node_type' WHERE type_kind IS NULL"))
    op.alter_column('node_types', 'type_kind', nullable=False)
    
    # Extend workflows table
    op.add_column('workflows', sa.Column('workflow_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('workflows', sa.Column('template_id', sa.String(length=255), nullable=True))
    
    # Add foreign key for template_id
    op.create_foreign_key(
        'fk_workflows_template_id',
        'workflows', 'node_types',
        ['template_id'], ['id']
    )
    
    # Extend workflow_nodes table
    op.add_column('workflow_nodes', sa.Column('node_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Set default values for new JSONB columns
    op.execute(text("UPDATE workflows SET workflow_config = '{}'::jsonb WHERE workflow_config IS NULL"))
    op.execute(text("UPDATE workflow_nodes SET node_config = '{}'::jsonb WHERE node_config IS NULL"))
    
    # Create indexes for template queries
    op.create_index('ix_node_types_type_kind', 'node_types', ['type_kind'])
    op.create_index('ix_node_types_category', 'node_types', ['category'])
    op.create_index('ix_node_types_is_public', 'node_types', ['is_public'])
    op.create_index('ix_workflows_template_id', 'workflows', ['template_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_workflows_template_id', table_name='workflows')
    op.drop_index('ix_node_types_is_public', table_name='node_types')
    op.drop_index('ix_node_types_category', table_name='node_types')
    op.drop_index('ix_node_types_type_kind', table_name='node_types')
    
    # Drop columns from workflow_nodes
    op.drop_column('workflow_nodes', 'node_config')
    
    # Drop columns from workflows
    op.drop_constraint('fk_workflows_template_id', 'workflows', type_='foreignkey')
    op.drop_column('workflows', 'template_id')
    op.drop_column('workflows', 'workflow_config')
    
    # Drop columns from node_types
    op.drop_constraint('fk_node_types_parent_template_id', 'node_types', type_='foreignkey')
    op.drop_constraint('fk_node_types_workflow_id', 'node_types', type_='foreignkey')
    op.drop_column('node_types', 'usage_count')
    op.drop_column('node_types', 'is_public')
    op.drop_column('node_types', 'parent_template_id')
    op.drop_column('node_types', 'version')
    op.drop_column('node_types', 'output_ports')
    op.drop_column('node_types', 'input_ports')
    op.drop_column('node_types', 'node_env_template')
    op.drop_column('node_types', 'workflow_env_template')
    op.drop_column('node_types', 'workflow_id')
    op.drop_column('node_types', 'workflow_template_data')
    op.drop_column('node_types', 'node_template_data')
    op.drop_column('node_types', 'type_kind')

