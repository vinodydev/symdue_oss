# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""Add default MinIO storage configuration

Revision ID: add_default_minio_001
Revises: add_node_name_001
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid

# revision identifiers, used by Alembic.
revision = 'add_default_minio_001'
down_revision = 'add_storage_system'  # Must run after storage_configs table is created
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if storage_configs table exists (from add_storage_system migration)
    # If not, this migration will fail and should be run after add_storage_system
    connection = op.get_bind()
    
    # Check if table exists
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'storage_configs'
        )
    """))
    table_exists = result.scalar()
    
    if not table_exists:
        # Table doesn't exist yet, skip this migration
        # This will be handled when add_storage_system migration runs
        return
    
    # Insert default MinIO storage configuration
    # Generate a deterministic UUID for the default storage config
    # Using a fixed namespace UUID based on the name "Default File Storage"
    default_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "graphmind-default-file-storage"))
    
    # MinIO configuration
    minio_config = {
        "endpoint": "http://minio:9000",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "bucket_name": "graphmind-files",
        "region": "us-east-1",
        "use_ssl": False
    }
    
    # Insert default MinIO storage configuration
    import json
    
    config_json = json.dumps(minio_config).replace("'", "''")  # Escape single quotes
    
    # Use direct SQL with formatted values
    op.execute(text(f"""
        INSERT INTO storage_configs (id, name, storage_type, config, enabled, created_at, updated_at)
        VALUES (
            '{default_id}'::uuid,
            'Default File Storage',
            'minio',
            '{config_json}'::jsonb,
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT (name) DO NOTHING
    """))


def downgrade() -> None:
    # Remove default MinIO storage configuration
    op.execute(text("""
        DELETE FROM storage_configs 
        WHERE name = 'Default File Storage' AND storage_type = 'minio'
    """))

