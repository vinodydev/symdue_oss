# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Node Type API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from database.connection import get_db
from database.models import NodeType, Workflow, WorkflowNode, WorkflowEdge
from utils.template_helpers import (
    extract_env_vars_from_code,
    is_workflow_level_var,
    is_node_level_var,
    identify_input_nodes,
    identify_output_nodes,
    build_input_ports,
    build_output_ports,
    serialize_node,
    serialize_edge,
    detect_circular_dependency
)
from utils.storage_helpers import storage_config_to_env_vars
from database.models import StorageConfig
from schemas.node_type import (
    NodeTypeCreate, 
    NodeTypeResponse,
    NodeTypeUpdate,
    SaveNodeAsTemplateRequest,
    SaveTemplateFromWorkflowRequest,
    CreateNodeFromTemplateRequest,
    SaveWorkflowAsTemplateRequest,
    CreateWorkflowFromTemplateRequest
)
from utils.template_helpers import (
    extract_env_vars_from_code,
    is_workflow_level_var,
    is_node_level_var
)
import uuid

router = APIRouter()


def _build_workflow_template_data_from_workflow(
    db: Session,
    workflow_id: UUID,
    keep_original_workflow_id: Optional[str] = None,
) -> dict:
    """Build workflow_template_data dict from an existing workflow (nodes + edges). Used by save-template-from-workflow and sync-from-workflow."""
    workflow = db.query(Workflow).filter_by(id=workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    nodes = db.query(WorkflowNode).filter_by(workflow_id=workflow_id, deleted_at=None).all()
    edges = db.query(WorkflowEdge).filter_by(workflow_id=workflow_id, deleted_at=None).all()
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")

    all_workflow_env_vars = set()
    all_node_env_vars = set()
    for node in nodes:
        python_code = node.config.get("python_code", "") or node.config.get("code", "")
        if python_code:
            used = extract_env_vars_from_code(python_code)
            for env_var in used:
                if is_workflow_level_var(env_var):
                    all_workflow_env_vars.add(env_var)
                elif is_node_level_var(env_var):
                    all_node_env_vars.add(env_var)
                else:
                    all_workflow_env_vars.add(env_var)

    workflow_env_template = {}
    for env_var in all_workflow_env_vars:
        workflow_env_template[env_var] = {
            "type": "string",
            "title": env_var.replace("_", " ").title(),
            "description": f"Workflow-level: {env_var}",
            "default": workflow.workflow_config.get(env_var, "") if workflow.workflow_config else "",
            "required": False,
        }
    node_env_template = {}
    for env_var in all_node_env_vars:
        node_env_template[env_var] = {
            "type": "string",
            "title": env_var.replace("_", " ").title(),
            "description": f"Node-level: {env_var}",
            "default": "",
            "required": False,
        }

    input_nodes = identify_input_nodes(nodes, edges)
    output_nodes = identify_output_nodes(nodes, edges)
    input_ports = build_input_ports(input_nodes)
    output_ports = build_output_ports(output_nodes)

    storage_requirements = {}
    storage_type_descriptions = {
        "postgresql": "PostgreSQL database",
        "redis": "Redis cache",
        "mongodb": "MongoDB database",
        "chroma": "ChromaDB vector store",
        "minio": "MinIO object storage",
        "s3": "S3-compatible storage",
        "local_file": "Local file storage",
    }
    for node in nodes:
        storage_configs = node.config.get("storage_configs", {})
        for alias, storage_info in storage_configs.items():
            storage_id = storage_info.get("storage_id")
            if storage_id:
                storage = db.query(StorageConfig).filter_by(id=storage_id, deleted_at=None).first()
                if storage:
                    st = storage.storage_type
                    if st not in storage_requirements:
                        storage_requirements[st] = {
                            "count": 0,
                            "description": storage_type_descriptions.get(st, f"{st} storage"),
                            "required": True,
                            "nodes_using": [],
                        }
                    storage_requirements[st]["count"] += 1
                    if node.name not in storage_requirements[st]["nodes_using"]:
                        storage_requirements[st]["nodes_using"].append(node.name)
                    storage_env = storage_config_to_env_vars(storage)
                    for key, value in storage_env.items():
                        if key not in workflow_env_template:
                            workflow_env_template[key] = {
                                "type": "string",
                                "title": key.replace("_", " ").title(),
                                "description": f"Storage config: {key}",
                                "default": value,
                                "required": False,
                            }
    for st in storage_requirements:
        storage_requirements[st]["count"] = 1

    serialized_nodes = [serialize_node(n) for n in nodes]
    serialized_edges = [serialize_edge(e) for e in edges]

    data = {
        "nodes": serialized_nodes,
        "edges": serialized_edges,
        "workflow_env_template": workflow_env_template,
        "node_env_template": node_env_template,
        "input_ports": input_ports,
        "output_ports": output_ports,
        "storage_requirements": storage_requirements,
    }
    if keep_original_workflow_id:
        data["original_workflow_id"] = keep_original_workflow_id
    return data


def _node_type_to_response(node_type: NodeType) -> dict:
    """Build the same response shape as get_node_type for a given NodeType instance."""
    response_data = {
        "id": node_type.id,
        "category": node_type.category,
        "name": node_type.name,
        "description": node_type.description,
        "icon": node_type.icon,
        "is_builtin": node_type.is_builtin,
        "default_config": node_type.default_config,
        "config_schema": node_type.config_schema if node_type.config_schema is not None else {},
    }
    if hasattr(node_type, "type_kind"):
        response_data["type_kind"] = node_type.type_kind
    if hasattr(node_type, "node_template_data"):
        response_data["node_template_data"] = node_type.node_template_data
    if hasattr(node_type, "workflow_template_data"):
        response_data["workflow_template_data"] = node_type.workflow_template_data
    if hasattr(node_type, "workflow_env_template"):
        response_data["workflow_env_template"] = node_type.workflow_env_template
    if hasattr(node_type, "node_env_template"):
        response_data["node_env_template"] = node_type.node_env_template
    if hasattr(node_type, "is_public"):
        response_data["is_public"] = node_type.is_public
    if hasattr(node_type, "usage_count"):
        response_data["usage_count"] = node_type.usage_count
    if hasattr(node_type, "workflow_id") and node_type.workflow_id is not None:
        response_data["workflow_id"] = str(node_type.workflow_id)
    return response_data


@router.get("")
async def list_node_types(
    category: Optional[str] = None,
    is_builtin: Optional[bool] = None,
    type_kind: Optional[str] = None,  # NEW: Filter by type_kind
    db: Session = Depends(get_db)
):
    """List all node types"""
    query = db.query(NodeType).filter(NodeType.is_active == True)
    
    if category:
        query = query.filter(NodeType.category == category)
    if is_builtin is not None:
        query = query.filter(NodeType.is_builtin == is_builtin)
    if type_kind:
        query = query.filter(NodeType.type_kind == type_kind)
    
    node_types = query.order_by(NodeType.category, NodeType.name).all()
    
    # Use Pydantic schema for proper serialization
    from schemas.node_type import NodeTypeResponse
    return [NodeTypeResponse.model_validate(nt).model_dump() for nt in node_types]


@router.get("/{node_type_id}")
async def get_node_type(
    node_type_id: str,
    db: Session = Depends(get_db)
):
    """Get a node type by ID"""
    node_type = db.query(NodeType).filter(
        NodeType.id == node_type_id,
        NodeType.is_active == True
    ).first()
    
    if not node_type:
        raise HTTPException(status_code=404, detail="Node type not found")
    
    # Ensure config_schema is always included in response (even if None)
    response_data = {
        "id": node_type.id,
        "category": node_type.category,
        "name": node_type.name,
        "description": node_type.description,
        "icon": node_type.icon,
        "is_builtin": node_type.is_builtin,
        "default_config": node_type.default_config,
        "config_schema": node_type.config_schema if node_type.config_schema is not None else {}
    }
    # Include new fields if present
    if hasattr(node_type, 'type_kind'):
        response_data["type_kind"] = node_type.type_kind
    if hasattr(node_type, 'node_template_data'):
        response_data["node_template_data"] = node_type.node_template_data
    if hasattr(node_type, 'workflow_template_data'):
        response_data["workflow_template_data"] = node_type.workflow_template_data
    if hasattr(node_type, 'workflow_env_template'):
        response_data["workflow_env_template"] = node_type.workflow_env_template
    if hasattr(node_type, 'node_env_template'):
        response_data["node_env_template"] = node_type.node_env_template
    if hasattr(node_type, 'is_public'):
        response_data["is_public"] = node_type.is_public
    if hasattr(node_type, 'usage_count'):
        response_data["usage_count"] = node_type.usage_count
    if hasattr(node_type, 'workflow_id') and node_type.workflow_id is not None:
        response_data["workflow_id"] = str(node_type.workflow_id)
    return response_data


@router.put("/{node_type_id}")
async def update_node_type(
    node_type_id: str,
    payload: NodeTypeUpdate,
    db: Session = Depends(get_db)
):
    """Update a node type (partial update). Built-in types allow only description and icon."""
    node_type = db.query(NodeType).filter(
        NodeType.id == node_type_id,
        NodeType.is_active == True
    ).first()
    if not node_type:
        raise HTTPException(status_code=404, detail="Node type not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return await get_node_type(node_type_id, db)

    if node_type.is_builtin:
        allowed = {"description", "icon"}
        data = {k: v for k, v in data.items() if k in allowed}

    for key, value in data.items():
        if hasattr(node_type, key):
            setattr(node_type, key, value)

    db.commit()
    db.refresh(node_type)
    return await get_node_type(node_type_id, db)


@router.delete("/{node_type_id}", status_code=204)
async def delete_node_type(
    node_type_id: str,
    db: Session = Depends(get_db)
):
    """Soft-delete a node type. Only non-built-in types can be deleted."""
    node_type = db.query(NodeType).filter(NodeType.id == node_type_id).first()
    if not node_type:
        raise HTTPException(status_code=404, detail="Node type not found")
    if node_type.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in node type")
    node_type.is_active = False
    db.commit()


@router.post("", response_model=NodeTypeResponse, status_code=201)
async def create_node_type(
    node_type: NodeTypeCreate,
    db: Session = Depends(get_db)
):
    """Create a custom node type"""
    # Use provided ID or generate from name
    node_id = node_type.id if node_type.id else node_type.name.lower().replace(" ", "-")
    
    # Check if ID already exists
    existing = db.query(NodeType).filter(NodeType.id == node_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Node type ID already exists")
    
    db_node_type = NodeType(
        id=node_id,
        category=node_type.category,
        name=node_type.name,
        description=node_type.description,
        icon=node_type.icon,
        default_config=node_type.default_config,
        config_schema=node_type.config_schema,
        is_builtin=False
    )
    db.add(db_node_type)
    db.commit()
    db.refresh(db_node_type)
    return db_node_type


@router.post("/from-node/{node_id}")
async def save_node_as_template(
    node_id: UUID,
    request: SaveNodeAsTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    Save an existing node as a reusable node type template.
    
    Returns:
    - node_type_id: ID of created template
    - workflow_env_vars: List of required workflow-level env vars
    - node_env_vars: List of required node-level env vars
    """
    # Get node
    node = db.query(WorkflowNode).filter_by(id=node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    workflow = db.query(Workflow).filter_by(id=node.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Extract environment variables from code
    python_code = node.config.get("python_code", "") or node.config.get("code", "")
    used_env_vars = extract_env_vars_from_code(python_code)
    
    # Categorize env vars (workflow-level vs node-level)
    workflow_env_template = {}
    node_env_template = {}
    
    for env_var in used_env_vars:
        if is_workflow_level_var(env_var):  # S3_BUCKET, DATABASE_URL, etc.
            workflow_env_template[env_var] = {
                "type": "string",
                "title": env_var.replace("_", " ").title(),
                "description": f"Workflow-level: {env_var}",
                "default": workflow.workflow_config.get(env_var, "") if workflow.workflow_config else "",
                "required": True,
            }
        elif is_node_level_var(env_var):  # NODE_TIMEOUT, etc.
            node_env_template[env_var] = {
                "type": "string",
                "title": env_var.replace("_", " ").title(),
                "description": f"Node-level: {env_var}",
                "default": node.node_config.get(env_var, "") if node.node_config else "",
                "required": False,
            }
        else:
            # Default to workflow-level for ambiguous vars
            workflow_env_template[env_var] = {
                "type": "string",
                "title": env_var.replace("_", " ").title(),
                "description": f"Workflow-level: {env_var}",
                "default": workflow.workflow_config.get(env_var, "") if workflow.workflow_config else "",
                "required": False,
            }
    
    # Build config schema
    config_schema = {
        "type": "object",
        "properties": {
            "workflow_env": {
                "type": "object",
                "title": "Workflow Environment Variables",
                "properties": workflow_env_template,
                "required": [k for k, v in workflow_env_template.items() if v.get("required", False)]
            },
            "node_env": {
                "type": "object",
                "title": "Node Environment Variables",
                "properties": node_env_template,
            }
        }
    }
    
    # Create node type
    node_type_id = f"template-{uuid.uuid4().hex[:12]}"
    node_type = NodeType(
        id=node_type_id,
        category="node_template",
        type_kind="node_template",
        name=request.template_name,
        description=request.template_description,
        node_template_data={
            "python_code": python_code,
            "original_config": node.config.copy() if node.config else {},  # Save FULL original config (code, name, requirements, storages, etc.)
            "workflow_env_template": workflow_env_template,
            "node_env_template": node_env_template,
            "used_env_vars": list(used_env_vars),
            "original_node_id": str(node_id),
            "original_node_type_id": node.node_type_id,
        },
        config_schema=config_schema,
        default_config=node.config.copy() if node.config else {},  # Store original node config as default
        workflow_env_template=workflow_env_template,
        node_env_template=node_env_template,
        is_public=request.is_public,
        is_builtin=False,
    )
    
    db.add(node_type)
    db.commit()
    db.refresh(node_type)
    
    return {
        "node_type_id": node_type_id,
        "workflow_env_vars": list(workflow_env_template.keys()),
        "node_env_vars": list(node_env_template.keys()),
    }


@router.post("/from-workflow/{workflow_id}")
async def save_workflow_as_template(
    workflow_id: UUID,
    request: SaveWorkflowAsTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    Save an existing workflow as a reusable workflow template.
    
    Returns:
    - node_type_id: ID of created template
    - workflow_env_vars: List of required workflow-level env vars
    - input_ports: List of input port definitions
    - output_ports: List of output port definitions
    """
    # Get workflow
    workflow = db.query(Workflow).filter_by(id=workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get all nodes and edges
    nodes = db.query(WorkflowNode).filter_by(
        workflow_id=workflow_id,
        deleted_at=None
    ).all()
    
    edges = db.query(WorkflowEdge).filter_by(
        workflow_id=workflow_id,
        deleted_at=None
    ).all()
    
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")
    
    # Extract environment variables from all Python nodes
    all_workflow_env_vars = set()
    all_node_env_vars = set()
    
    for node in nodes:
        python_code = node.config.get("python_code", "") or node.config.get("code", "")
        if python_code:
            used_env_vars = extract_env_vars_from_code(python_code)
            for env_var in used_env_vars:
                if is_workflow_level_var(env_var):
                    all_workflow_env_vars.add(env_var)
                elif is_node_level_var(env_var):
                    all_node_env_vars.add(env_var)
                else:
                    # Default to workflow-level
                    all_workflow_env_vars.add(env_var)
    
    # Build workflow env template
    workflow_env_template = {}
    for env_var in all_workflow_env_vars:
        workflow_env_template[env_var] = {
            "type": "string",
            "title": env_var.replace("_", " ").title(),
            "description": f"Workflow-level: {env_var}",
            "default": workflow.workflow_config.get(env_var, "") if workflow.workflow_config else "",
            "required": False,
        }
    
    # Build node env template
    node_env_template = {}
    for env_var in all_node_env_vars:
        node_env_template[env_var] = {
            "type": "string",
            "title": env_var.replace("_", " ").title(),
            "description": f"Node-level: {env_var}",
            "default": "",
            "required": False,
        }
    
    # Identify input/output nodes
    input_nodes = identify_input_nodes(nodes, edges)
    output_nodes = identify_output_nodes(nodes, edges)
    
    input_ports = build_input_ports(input_nodes)
    output_ports = build_output_ports(output_nodes)
    
    # Collect storage dependencies and group by type
    storage_requirements = {}  # {storage_type: {count, description, required, nodes_using}}
    storage_type_descriptions = {
        "postgresql": "PostgreSQL database",
        "redis": "Redis cache",
        "mongodb": "MongoDB database",
        "chroma": "ChromaDB vector store",
        "minio": "MinIO object storage",
        "s3": "S3-compatible storage",
        "local_file": "Local file storage",
    }
    
    for node in nodes:
        storage_configs = node.config.get("storage_configs", {})
        for alias, storage_info in storage_configs.items():
            storage_id = storage_info.get("storage_id")
            if storage_id:
                storage = db.query(StorageConfig).filter_by(id=storage_id, deleted_at=None).first()
                if storage:
                    storage_type = storage.storage_type
                    
                    # Group by storage type
                    if storage_type not in storage_requirements:
                        storage_requirements[storage_type] = {
                            "count": 0,
                            "description": storage_type_descriptions.get(storage_type, f"{storage_type} storage"),
                            "required": True,  # Default to required
                            "nodes_using": [],  # Track which nodes use this storage
                        }
                    
                    storage_requirements[storage_type]["count"] += 1
                    if node.name not in storage_requirements[storage_type]["nodes_using"]:
                        storage_requirements[storage_type]["nodes_using"].append(node.name)
                    
                    # Add storage env vars to workflow template
                    storage_env = storage_config_to_env_vars(storage)
                    for key, value in storage_env.items():
                        if key not in workflow_env_template:
                            workflow_env_template[key] = {
                                "type": "string",
                                "title": key.replace("_", " ").title(),
                                "description": f"Storage config: {key}",
                                "default": value,
                                "required": False,
                            }
    
    # Simplify: one storage instance per type (even if used by multiple nodes)
    for storage_type in storage_requirements:
        storage_requirements[storage_type]["count"] = 1
    
    # Serialize nodes and edges
    serialized_nodes = [serialize_node(node) for node in nodes]
    serialized_edges = [serialize_edge(edge) for edge in edges]
    
    # Build config schema with storage_mapping support
    storage_mapping_schema = {}
    for storage_type, requirement in storage_requirements.items():
        storage_mapping_schema[storage_type] = {
            "type": "string",
            "title": f"{storage_type.replace('_', ' ').title()} Storage",
            "description": requirement.get("description", ""),
            "required": requirement.get("required", True),
        }
    
    config_schema = {
        "type": "object",
        "properties": {
            "workflow_env": {
                "type": "object",
                "title": "Workflow Environment Variables",
                "properties": workflow_env_template,
            },
            "storage_mapping": {
                "type": "object",
                "title": "Storage Configuration",
                "description": "Select storage instances for this sub-workflow",
                "properties": storage_mapping_schema,
                "required": [k for k, v in storage_mapping_schema.items() if v.get("required", True)],
            }
        }
    }
    
    # Create node type for workflow template
    node_type_id = f"workflow-template-{uuid.uuid4().hex[:12]}"
    node_type = NodeType(
        id=node_type_id,
        category="workflow_template",
        type_kind="workflow_template",
        name=request.template_name,
        description=request.template_description,
        workflow_template_data={
            "nodes": serialized_nodes,
            "edges": serialized_edges,
            "workflow_env_template": workflow_env_template,
            "node_env_template": node_env_template,
            "input_ports": input_ports,
            "output_ports": output_ports,
            "storage_requirements": storage_requirements,  # NEW: Storage dependencies
            "original_workflow_id": str(workflow_id),
        },
        config_schema=config_schema,
        default_config={
            "workflow_env": workflow_env_template,
        },
        workflow_env_template=workflow_env_template,
        node_env_template=node_env_template,
        input_ports=input_ports,
        output_ports=output_ports,
        workflow_id=workflow_id,  # Reference to original workflow
        is_public=request.is_public,
        is_builtin=False,
    )
    
    db.add(node_type)
    db.commit()
    db.refresh(node_type)
    
    return {
        "node_type_id": node_type_id,
        "workflow_env_vars": list(workflow_env_template.keys()),
        "input_ports": input_ports,
        "output_ports": output_ports,
        "storage_requirements": storage_requirements,  # NEW: Return storage requirements
    }


@router.post("/{node_type_id}/create-edit-copy")
async def create_template_edit_copy(
    node_type_id: str,
    db: Session = Depends(get_db)
):
    """Return or create a workflow for editing this template's snapshot. Reuses existing edit-copy if one exists (same template_id + name 'Edit: {template.name}')."""
    template = db.query(NodeType).filter(
        NodeType.id == node_type_id,
        NodeType.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Node type not found")
    if template.type_kind != "workflow_template":
        raise HTTPException(status_code=400, detail="Not a workflow template")
    template_data = template.workflow_template_data
    if not template_data:
        raise HTTPException(status_code=400, detail="Template has no workflow data")

    edit_name = f"Edit: {template.name}"
    existing = (
        db.query(Workflow)
        .filter(
            Workflow.template_id == node_type_id,
            Workflow.name == edit_name,
            Workflow.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        return {"workflow_id": str(existing.id)}

    from utils.workflow_from_template import create_workflow_from_template_data
    new_workflow = create_workflow_from_template_data(
        db,
        template_data,
        workflow_name=edit_name,
        workflow_config={},
        template_id=node_type_id,
        attach_storage=False,
    )
    return {"workflow_id": str(new_workflow.id)}


@router.post("/{node_type_id}/save-template-from-workflow")
async def save_template_from_workflow(
    node_type_id: str,
    request: SaveTemplateFromWorkflowRequest,
    db: Session = Depends(get_db)
):
    """Overwrite the template's snapshot with the given workflow's current state (e.g. after editing the edit copy)."""
    template = db.query(NodeType).filter(
        NodeType.id == node_type_id,
        NodeType.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Node type not found")
    if template.type_kind != "workflow_template":
        raise HTTPException(status_code=400, detail="Not a workflow template")

    keep_original = None
    if template.workflow_template_data:
        keep_original = template.workflow_template_data.get("original_workflow_id")
    if not keep_original and template.workflow_id:
        keep_original = str(template.workflow_id)

    data = _build_workflow_template_data_from_workflow(db, request.workflow_id, keep_original_workflow_id=keep_original)
    template.workflow_template_data = data
    db.commit()
    db.refresh(template)
    return _node_type_to_response(template)


@router.post("/{node_type_id}/sync-from-workflow")
async def sync_template_from_workflow(
    node_type_id: str,
    db: Session = Depends(get_db)
):
    """Overwrite the template's snapshot from the original workflow (template.workflow_id). 404 if no original."""
    template = db.query(NodeType).filter(
        NodeType.id == node_type_id,
        NodeType.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Node type not found")
    if template.type_kind != "workflow_template":
        raise HTTPException(status_code=400, detail="Not a workflow template")

    original_id = template.workflow_id
    if not original_id and template.workflow_template_data:
        orig = template.workflow_template_data.get("original_workflow_id")
        if orig:
            original_id = UUID(orig)
    if not original_id:
        raise HTTPException(status_code=404, detail="No original workflow to sync from")

    data = _build_workflow_template_data_from_workflow(db, original_id, keep_original_workflow_id=str(original_id))
    template.workflow_template_data = data
    db.commit()
    db.refresh(template)
    return _node_type_to_response(template)
