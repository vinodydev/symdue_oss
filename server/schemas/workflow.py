# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Workflow (Workspace) schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

# Forward references - will be resolved after all schemas are loaded
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from schemas.node import NodeResponse
    from schemas.edge import EdgeResponse


class WorkflowCreate(BaseModel):
    """Schema for creating a new workflow"""
    name: Optional[str] = "Untitled Workflow"


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow"""
    name: Optional[str] = None
    transform: Optional[Dict[str, Any]] = None
    workflow_config: Optional[Dict[str, str]] = None  # NEW: Workflow-level env vars


class WorkflowResponse(BaseModel):
    """Schema for workflow response"""
    id: UUID
    name: str
    transform: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    version: int
    workflow_config: Optional[Dict[str, str]] = None  # NEW: Workflow-level env vars
    execution_config: Optional[Dict[str, Any]] = None  # Per-workflow timeouts
    template_id: Optional[str] = None  # NEW: Template ID if created from template
    
    class Config:
        from_attributes = True


class WorkflowConfigUpdate(BaseModel):
    """Schema for updating workflow config"""
    config: Dict[str, str]  # Environment variables


class ExecutionConfigSchema(BaseModel):
    """Per-workflow execution timeouts and limits."""
    graph_activity_timeout_minutes: Optional[int] = 30
    heartbeat_timeout_minutes: Optional[int] = 5
    default_node_timeout_seconds: Optional[int] = 600
    max_node_timeout_seconds: Optional[int] = 3600


class ExecutionConfigUpdate(BaseModel):
    """Schema for updating workflow execution config."""
    execution_config: Optional[Dict[str, Any]] = None  # Partial update; omit keys to keep current


class WorkflowDetail(WorkflowResponse):
    """Schema for workflow with nodes and edges"""
    nodes: List['NodeResponse']  # type: ignore
    edges: List['EdgeResponse']  # type: ignore


# --- Workflow Export/Import as JSON ---

class WorkflowExportNode(BaseModel):
    """Serialized node for export"""
    id: str
    name: str
    node_type_id: str
    ui_x: float
    ui_y: float
    config: Dict[str, Any] = {}
    node_config: Dict[str, Any] = {}


class WorkflowExportEdge(BaseModel):
    """Serialized edge for export"""
    source_node_id: str
    target_node_id: str
    weight: float = 1.0
    source_handle: Optional[str] = None  # "true" | "false" for condition-node branches


class WorkflowExport(BaseModel):
    """Schema for exported workflow JSON"""
    version: int = 1
    name: str
    transform: Dict[str, Any] = {"x": 0, "y": 0, "k": 1}
    workflow_config: Dict[str, Any] = {}
    nodes: List[WorkflowExportNode]
    edges: List[WorkflowExportEdge]


class WorkflowImport(BaseModel):
    """Schema for importing workflow from JSON"""
    version: int = 1
    name: Optional[str] = "Imported Workflow"
    transform: Optional[Dict[str, Any]] = None
    workflow_config: Optional[Dict[str, Any]] = None
    nodes: List[WorkflowExportNode]
    edges: List[WorkflowExportEdge]
