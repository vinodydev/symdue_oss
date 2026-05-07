# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Node Type schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from uuid import UUID


class NodeTypeCreate(BaseModel):
    """Schema for creating a new node type"""
    id: Optional[str] = None  # Optional: if not provided, will be generated from name
    name: str
    description: Optional[str] = None
    category: str
    icon: Optional[str] = None
    default_config: Dict[str, Any]
    config_schema: Optional[Dict[str, Any]] = None


class NodeTypeResponse(BaseModel):
    """Schema for node type response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    category: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_builtin: bool
    default_config: Optional[Dict[str, Any]] = None
    config_schema: Optional[Dict[str, Any]] = None
    # NEW: Template-specific fields
    type_kind: Optional[str] = None
    node_template_data: Optional[Dict[str, Any]] = None
    workflow_template_data: Optional[Dict[str, Any]] = None
    workflow_env_template: Optional[Dict[str, Any]] = None
    node_env_template: Optional[Dict[str, Any]] = None
    input_ports: Optional[List[Dict[str, Any]]] = None
    output_ports: Optional[List[Dict[str, Any]]] = None
    is_public: Optional[bool] = False
    usage_count: Optional[int] = 0


class NodeTypeUpdate(BaseModel):
    """Schema for updating a node type (partial update)."""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    default_config: Optional[Dict[str, Any]] = None
    config_schema: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class SaveNodeAsTemplateRequest(BaseModel):
    """Schema for saving node as template"""
    template_name: str
    template_description: Optional[str] = None
    is_public: bool = False


class CreateNodeFromTemplateRequest(BaseModel):
    """Schema for creating node from template"""
    template_id: str
    node_name: str
    workflow_env: Optional[Dict[str, str]] = None
    node_env: Optional[Dict[str, str]] = None
    storages: Optional[List[Dict[str, str]]] = None  # Storage configs [{"alias": "name", "storage_id": "id"}]
    requirements: Optional[str] = None  # Python requirements
    config_overrides: Optional[Dict[str, Any]] = None  # Other config overrides


class SaveWorkflowAsTemplateRequest(BaseModel):
    """Schema for saving workflow as template"""
    template_name: str
    template_description: Optional[str] = None
    is_public: bool = False


class CreateWorkflowFromTemplateRequest(BaseModel):
    """Schema for creating workflow from template"""
    template_id: str
    workflow_name: str
    workflow_env: Optional[Dict[str, str]] = None


class CreateSubWorkflowNodeRequest(BaseModel):
    """Schema for creating sub-workflow node from template"""
    template_id: str
    node_name: str
    workflow_env: Optional[Dict[str, str]] = None
    storage_mapping: Optional[Dict[str, str]] = None  # {storage_type: storage_name}


class CreateWorkflowReferenceNodeRequest(BaseModel):
    """Schema for creating a workflow node that references another workflow by ID (live reference)."""
    workflow_id: UUID
    node_name: str
    x: float = 0.0
    y: float = 0.0


class SaveTemplateFromWorkflowRequest(BaseModel):
    """Schema for saving template snapshot from a workflow (e.g. edit copy)."""
    workflow_id: UUID
