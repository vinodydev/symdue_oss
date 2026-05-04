"""
Node schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class NodeCreate(BaseModel):
    """Schema for creating a new node"""
    node_type_id: str
    name: Optional[str] = None  # If not provided, will be auto-generated
    x: float
    y: float
    config_overrides: Optional[Dict[str, Any]] = {}


class NodeUpdate(BaseModel):
    """Schema for updating a node"""
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    node_config: Optional[Dict[str, str]] = None  # NEW: Node-level env vars


class NodePositionUpdate(BaseModel):
    """Schema for updating node position"""
    x: float
    y: float


class NodeResponse(BaseModel):
    """Schema for node response"""
    model_config = {"from_attributes": True, "populate_by_name": True}
    
    id: UUID
    node_type_id: str
    name: str
    x: float  # Serializes as "x" (not "ui_x")
    y: float  # Serializes as "y" (not "ui_y")
    config: Dict[str, Any]
    node_config: Optional[Dict[str, str]] = None  # NEW: Node-level env vars
    created_at: datetime


class NodeConfigUpdate(BaseModel):
    """Schema for updating node config"""
    node_config: Dict[str, str]  # Node-level environment variables

