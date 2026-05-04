"""
Storage configuration model
"""
from sqlalchemy import Column, String, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class StorageConfig(Base):
    """Storage backend configuration"""
    __tablename__ = "storage_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)  # User-friendly name
    storage_type = Column(String(50), nullable=False)  # postgresql, redis, mongodb, chroma, local_file, minio, s3
    config = Column(JSONB, nullable=False)  # Storage-specific configuration
    enabled = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # Index for lookups
    __table_args__ = (
        Index('ix_storage_configs_name', 'name', unique=True),
    )

