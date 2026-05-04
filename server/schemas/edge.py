"""
Edge schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


SourceHandleType = Literal["true", "false"]


class EdgeCreate(BaseModel):
    """Schema for creating a new edge"""
    source: UUID
    target: UUID
    weight: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)  # KEY: Weighted Intelligence
    source_handle: Optional[SourceHandleType] = None  # "true" | "false" for condition-node branches


class EdgeUpdate(BaseModel):
    """Schema for updating an edge"""
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_handle: Optional[SourceHandleType] = None


class EdgeResponse(BaseModel):
    """Schema for edge response"""
    id: UUID
    source: UUID
    target: UUID
    weight: float  # KEY: Weighted Intelligence (0.0-1.0)
    source_handle: Optional[str] = None  # "true" | "false" for condition-node branches
    created_at: datetime
    
    class Config:
        from_attributes = True

