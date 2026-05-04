"""
Storage schemas
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime


class StorageConfigBase(BaseModel):
    name: str = Field(..., description="User-friendly storage name")
    storage_type: str = Field(..., description="Storage type: postgresql, redis, mongodb, chroma, local_file, minio, s3")
    config: Dict[str, Any] = Field(..., description="Storage-specific configuration")
    enabled: bool = Field(default=True, description="Whether storage is enabled")


class StorageConfigCreate(StorageConfigBase):
    pass


class StorageConfigUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class StorageConfigResponse(StorageConfigBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StorageReference(BaseModel):
    """Storage reference for node attachment"""
    storage_id: str
    alias: Optional[str] = None

