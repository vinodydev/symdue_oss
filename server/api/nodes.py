# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Node API endpoints
"""
import re
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID
from database.connection import get_db
from database.models import Workflow, WorkflowNode, WorkflowEdge
from schemas.node import NodeCreate, NodeUpdate, NodePositionUpdate, NodeResponse, NodeConfigUpdate
from schemas.node_type import CreateNodeFromTemplateRequest, CreateSubWorkflowNodeRequest, CreateWorkflowReferenceNodeRequest
from database.models import NodeType, StorageConfig

router = APIRouter()


def _generate_node_name(node_type_id: str, node_id: UUID) -> str:
    """Generate a default node name if not provided"""
    short_id = str(node_id)[:8]
    return f"node_{node_type_id}_{short_id}"


def _validate_node_name(name: str) -> None:
    """
    Validate node name format.
    Must be: alphanumeric + underscore, 1-255 chars, not empty.
    """
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Node name cannot be empty")
    
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="Node name must be 255 characters or less")
    
    # Allow alphanumeric, underscore, and hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise HTTPException(
            status_code=400,
            detail="Node name can only contain letters, numbers, underscores, and hyphens"
        )


def _check_name_uniqueness(
    db: Session,
    workflow_id: UUID,
    name: str,
    exclude_node_id: UUID = None
) -> None:
    """Check if node name is unique within the workflow"""
    query = db.query(WorkflowNode).filter(
        WorkflowNode.workflow_id == workflow_id,
        WorkflowNode.name == name,
        WorkflowNode.deleted_at.is_(None)
    )
    
    if exclude_node_id:
        query = query.filter(WorkflowNode.id != exclude_node_id)
    
    existing = query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Node name '{name}' already exists in this workflow"
        )


@router.post("/{workspace_id}/nodes", response_model=NodeResponse, status_code=201)
async def create_node(
    workspace_id: UUID,
    node: NodeCreate,
    db: Session = Depends(get_db)
):
    """Create a new node in a workspace"""
    # Verify workspace exists
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Merge default config with overrides
    from database.models import NodeType
    node_type = db.query(NodeType).filter(NodeType.id == node.node_type_id).first()
    if not node_type:
        raise HTTPException(status_code=404, detail="Node type not found")
    
    # === Handle workflow templates - expand all nodes + edges into current workflow ===
    if node_type.type_kind == "workflow_template" and node_type.workflow_template_data:
        template_data = node_type.workflow_template_data
        
        # Note: No circular dependency check needed here because we're expanding
        # (copying) nodes into the workflow, not creating a sub-workflow reference.
        # Circular dependency checks are only needed for sub-workflow node execution.
        
        serialized_nodes = template_data.get("nodes", [])
        serialized_edges = template_data.get("edges", [])
        
        if not serialized_nodes:
            raise HTTPException(status_code=400, detail="Workflow template has no nodes")
        
        # Calculate offset: position template nodes relative to drop position
        min_x = min((n.get("ui_x", 0) for n in serialized_nodes), default=0)
        min_y = min((n.get("ui_y", 0) for n in serialized_nodes), default=0)
        offset_x = node.x - min_x
        offset_y = node.y - min_y
        
        node_id_mapping = {}  # old_id -> new_node
        created_nodes = []
        
        for sn in serialized_nodes:
            old_id = sn["id"]
            
            # Create node with a temporary name first
            new_node = WorkflowNode(
                workflow_id=workspace_id,
                name="temp_expanding",
                node_type_id=sn["node_type_id"],
                ui_x=sn.get("ui_x", 0.0) + offset_x,
                ui_y=sn.get("ui_y", 0.0) + offset_y,
                config=sn.get("config", {}),
                node_config=sn.get("node_config", {}),
            )
            db.add(new_node)
            db.flush()  # Get new ID
            
            # Generate unique name using the new ID
            new_name = _generate_node_name(sn["node_type_id"], new_node.id)
            # Ensure uniqueness
            counter = 0
            candidate = new_name
            while db.query(WorkflowNode).filter(
                WorkflowNode.workflow_id == workspace_id,
                WorkflowNode.name == candidate,
                WorkflowNode.deleted_at.is_(None),
                WorkflowNode.id != new_node.id
            ).first():
                counter += 1
                candidate = f"{new_name}_{counter}"
            new_node.name = candidate
            
            node_id_mapping[old_id] = new_node
            created_nodes.append(new_node)
        
        # Create edges with remapped IDs
        for se in serialized_edges:
            source_node = node_id_mapping.get(se["source_node_id"])
            target_node = node_id_mapping.get(se["target_node_id"])
            if source_node and target_node:
                new_edge = WorkflowEdge(
                    workflow_id=workspace_id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    weight=se.get("weight", 1.0),
                )
                db.add(new_edge)
        
        # Increment template usage count
        node_type.usage_count = (node_type.usage_count or 0) + 1
        db.commit()
        
        # Return the first created node (frontend will reload to get all)
        first_node = created_nodes[0]
        db.refresh(first_node)
        return NodeResponse(
            id=first_node.id,
            node_type_id=first_node.node_type_id,
            name=first_node.name,
            x=first_node.ui_x if first_node.ui_x is not None else 0.0,
            y=first_node.ui_y if first_node.ui_y is not None else 0.0,
            config=first_node.config,
            node_config=first_node.node_config or {},
            created_at=first_node.created_at
        )
    
    # Detect if this is a node template and resolve to original node type + config
    actual_node_type_id = node.node_type_id
    if node_type.type_kind == "node_template" and node_type.node_template_data:
        template_data = node_type.node_template_data
        original_config = template_data.get("original_config", {})
        original_node_type_id = template_data.get("original_node_type_id", node.node_type_id)
        
        # Get the original node type's default config as base
        original_node_type = db.query(NodeType).filter(NodeType.id == original_node_type_id).first()
        config = original_node_type.default_config.copy() if original_node_type and original_node_type.default_config else {}
        
        # Merge in the saved original config (code, name, requirements, storages, etc.)
        config.update(original_config)
        
        # Apply any overrides from the request
        config.update(node.config_overrides)
        
        # Use the original node type ID so the frontend renders it correctly
        actual_node_type_id = original_node_type_id
        
        # Increment template usage count
        node_type.usage_count = (node_type.usage_count or 0) + 1
    else:
        config = node_type.default_config.copy() if node_type.default_config else {}
        config.update(node.config_overrides)
    
    # Generate or validate node name
    if node.name:
        _validate_node_name(node.name)
        _check_name_uniqueness(db, workspace_id, node.name)
        node_name = node.name
    else:
        # Generate temporary name, will be updated after commit
        node_name = None
    
    db_node = WorkflowNode(
        workflow_id=workspace_id,
        node_type_id=actual_node_type_id,  # Use original type for templates
        name=node_name or "temp",  # Temporary, will be updated
        ui_x=node.x,
        ui_y=node.y,
        config=config
    )
    db.add(db_node)
    db.flush()  # Get the ID without committing
    
    # If name wasn't provided, generate one now that we have the ID
    if not node.name:
        node_name = _generate_node_name(actual_node_type_id, db_node.id)
        # Check if generated name is unique (unlikely but possible)
        while True:
            existing = db.query(WorkflowNode).filter(
                WorkflowNode.workflow_id == workspace_id,
                WorkflowNode.name == node_name,
                WorkflowNode.deleted_at.is_(None),
                WorkflowNode.id != db_node.id
            ).first()
            if not existing:
                break
            # Append counter if collision
            node_name = f"{node_name}_1"
        db_node.name = node_name
    
    db.commit()
    db.refresh(db_node)
    # Map ui_x/ui_y to x/y for response (handle None values)
    return NodeResponse(
        id=db_node.id,
        node_type_id=db_node.node_type_id,
        name=db_node.name,
        x=db_node.ui_x if db_node.ui_x is not None else 0.0,
        y=db_node.ui_y if db_node.ui_y is not None else 0.0,
        config=db_node.config,
        node_config=db_node.node_config or {},
        created_at=db_node.created_at
    )


@router.get("/{workspace_id}/nodes", response_model=List[NodeResponse])
async def list_nodes(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """List all nodes in a workspace"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    nodes = db.query(WorkflowNode).filter(
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).all()
    
    # Map ui_x/ui_y to x/y for response (handle None values)
    return [
        NodeResponse(
            id=node.id,
            node_type_id=node.node_type_id,
            name=node.name,
            x=node.ui_x if node.ui_x is not None else 0.0,
            y=node.ui_y if node.ui_y is not None else 0.0,
            config=node.config,
            node_config=node.node_config or {},
            created_at=node.created_at
        )
        for node in nodes
    ]


@router.get("/{workspace_id}/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    workspace_id: UUID,
    node_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a node by ID"""
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Map ui_x/ui_y to x/y for response (handle None values)
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )


@router.patch("/{workspace_id}/nodes/{node_id}", response_model=NodeResponse)
async def update_node(
    workspace_id: UUID,
    node_id: UUID,
    node_update: NodeUpdate,
    db: Session = Depends(get_db)
):
    """Update a node's configuration"""
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Handle name update
    if node_update.name is not None:
        _validate_node_name(node_update.name)
        _check_name_uniqueness(db, workspace_id, node_update.name, exclude_node_id=node_id)
        node.name = node_update.name
    
    if node_update.config is not None:
        # Merge config instead of just updating (preserve existing keys)
        current_config = node.config.copy() if node.config else {}
        current_config.update(node_update.config)
        node.config = current_config
    
    if node_update.node_config is not None:
        # Update node-level environment variables
        node.node_config = node_update.node_config
    
    db.commit()
    db.refresh(node)
    # Map ui_x/ui_y to x/y for response (handle None values)
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )


@router.patch("/{workspace_id}/nodes/{node_id}/position", response_model=NodeResponse)
async def update_node_position(
    workspace_id: UUID,
    node_id: UUID,
    position: NodePositionUpdate,
    db: Session = Depends(get_db)
):
    """Update a node's position"""
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.ui_x = position.x
    node.ui_y = position.y
    
    db.commit()
    db.refresh(node)
    # Map ui_x/ui_y to x/y for response (handle None values)
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )


@router.delete("/{workspace_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    workspace_id: UUID,
    node_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete a node and cascade to connected edges."""
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    from sqlalchemy.sql import func
    from sqlalchemy import or_
    now = func.now()

    # Soft-delete the node
    node.deleted_at = now

    # Cascade: soft-delete all edges connected to this node
    db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None),
        or_(
            WorkflowEdge.source_node_id == node_id,
            WorkflowEdge.target_node_id == node_id,
        ),
    ).update({"deleted_at": now}, synchronize_session="fetch")

    db.commit()
    return None


@router.post("/{workspace_id}/nodes/{node_id}/test", status_code=200)
async def test_node(
    workspace_id: UUID,
    node_id: UUID,
    test_inputs: Dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db)
):
    """
    Test a node independently (pre-flight testing).
    
    This executes the node with the given inputs without adding it to a workflow.
    Used for validating node configuration before adding to graph.
    """
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Get node type
    from database.models import NodeType
    node_type = db.query(NodeType).filter(NodeType.id == node.node_type_id).first()
    if not node_type:
        raise HTTPException(status_code=404, detail="Node type not found")
    
    # TODO: Implement actual node execution logic
    # For now, return a mock response
    # In Phase 3, this will use the actual node executor
    try:
        # Mock execution based on node type
        result = {
            "node_id": str(node_id),
            "node_type_id": node.node_type_id,
            "status": "success",
            "output": None,
            "error": None,
            "execution_time_ms": 0,
        }
        
        if node_type.id == "input":
            # Input node just returns the value from config
            result["output"] = node.config.get("value", "")
        elif node_type.id == "custom-python":
            # Python node - would execute code here
            result["output"] = "Python execution not yet implemented"
            result["status"] = "pending"
        elif node_type.id == "custom-llm":
            # LLM node - would call LLM here
            result["output"] = "LLM execution not yet implemented"
            result["status"] = "pending"
        elif node_type.id == "memory":
            # Memory node - would retrieve from memory
            result["output"] = "Memory retrieval not yet implemented"
            result["status"] = "pending"
        else:
            result["output"] = f"Node type {node_type.id} execution not yet implemented"
            result["status"] = "pending"
        
        return result
    except Exception as e:
        return {
            "node_id": str(node_id),
            "node_type_id": node.node_type_id,
            "status": "error",
            "output": None,
            "error": str(e),
            "execution_time_ms": 0,
        }


@router.put("/{workspace_id}/nodes/{node_id}/config")
async def update_node_config(
    workspace_id: UUID,
    node_id: UUID,
    node_config: NodeConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update node-level environment variables"""
    node = db.query(WorkflowNode).filter(
        WorkflowNode.id == node_id,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.node_config = node_config.node_config
    db.commit()
    db.refresh(node)
    
    return {"node_id": str(node_id), "node_config": node.node_config}


@router.post("/{workspace_id}/nodes/from-template")
async def create_node_from_template(
    workspace_id: UUID,
    request: CreateNodeFromTemplateRequest,
    db: Session = Depends(get_db)
):
    """Create node from template - configure environment variables"""
    
    # Verify workspace exists
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get template
    template = db.query(NodeType).filter_by(id=request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.type_kind != "node_template":
        raise HTTPException(status_code=400, detail="Template is not a node template")
    
    template_data = template.node_template_data
    if not template_data:
        raise HTTPException(status_code=400, detail="Template data not found")
    
    # 1. Update workflow config with template's workflow env vars
    if request.workflow_env:
        current_workflow_config = workflow.workflow_config or {}
        updated_workflow_config = {**current_workflow_config, **request.workflow_env}
        workflow.workflow_config = updated_workflow_config
        db.commit()
    
    # 2. Create node with restored config structure
    python_code = template_data.get("python_code", "")
    original_node_type_id = template_data.get("original_node_type_id", "custom-python")
    original_config = template_data.get("original_config", {})
    
    # Get the original node type to get its default config structure
    original_node_type = db.query(NodeType).filter_by(id=original_node_type_id).first()
    if not original_node_type:
        raise HTTPException(status_code=404, detail="Original node type not found")
    
    # Start with the original node type's default config
    restored_config = original_node_type.default_config.copy() if original_node_type.default_config else {}
    
    # Merge in the saved config from template (this restores code, name, requirements, storages, etc.)
    restored_config.update(original_config)
    
    # Apply user-provided overrides
    if request.config_overrides:
        restored_config.update(request.config_overrides)
    
    # Override with user-provided values
    if python_code:
        restored_config["code"] = python_code
        if "python_code" not in restored_config:
            restored_config["python_code"] = python_code
    
    if request.requirements is not None:
        restored_config["requirements"] = request.requirements
    
    # Handle storages - they're stored in node.config["storages"] as array of {storage_id, alias}
    # Get storages from request or restore from original config
    storages_to_attach = []
    if request.storages:
        # Convert request format to config format
        storages_to_attach = [
            {
                "storage_id": str(s.get("storage_id") or s.get("id", "")),
                "alias": s.get("alias", "default")
            }
            for s in request.storages
            if s.get("storage_id") or s.get("id")
        ]
    elif "storages" in restored_config and isinstance(restored_config["storages"], list):
        # Keep original format if already in config
        storages_to_attach = restored_config["storages"]
    
    # Remove storages from config (we'll add them back in the correct format)
    restored_config.pop("storages", None)
    
    # Add storages back in the correct format for node.config["storages"]
    if storages_to_attach:
        restored_config["storages"] = storages_to_attach
    
    node = WorkflowNode(
        workflow_id=workspace_id,
        name=request.node_name,
        node_type_id=original_node_type_id,  # Use original type, not template ID
        ui_x=0.0,  # Default position
        ui_y=0.0,
        config=restored_config,
        node_config=request.node_env or {}
    )
    
    db.add(node)
    db.commit()
    db.refresh(node)
    
    # Increment template usage count
    template.usage_count = (template.usage_count or 0) + 1
    db.commit()
    
    # Map ui_x/ui_y to x/y for response (handle None values)
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )


@router.post("/{workspace_id}/nodes/from-workflow-template")
async def create_sub_workflow_node(
    workspace_id: UUID,
    request: CreateSubWorkflowNodeRequest,
    db: Session = Depends(get_db)
):
    """Create a sub-workflow node from a workflow template"""
    
    # Verify workspace exists
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get template
    template = db.query(NodeType).filter_by(id=request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.type_kind != "workflow_template":
        raise HTTPException(status_code=400, detail="Template is not a workflow template")
    
    template_data = template.workflow_template_data
    if not template_data:
        raise HTTPException(status_code=400, detail="Template data not found")
    
    # Check for circular dependencies
    if template.workflow_id:
        from utils.template_helpers import detect_circular_dependency
        if detect_circular_dependency(str(workspace_id), str(template.workflow_id), db=db):
            raise HTTPException(status_code=400, detail="Circular dependency detected: cannot use this template in its own workflow")
    
    # Get storage requirements
    storage_requirements = template_data.get("storage_requirements", {})
    
    # Auto-select or use provided storage_mapping
    storage_mapping = request.storage_mapping or {}
    final_storage_mapping = {}
    
    for storage_type, requirement in storage_requirements.items():
        if storage_type in storage_mapping:
            # Use provided mapping
            storage_name = storage_mapping[storage_type]
            storage = db.query(StorageConfig).filter_by(
                name=storage_name,
                storage_type=storage_type,
                deleted_at=None,
                enabled=True
            ).first()
            if storage:
                final_storage_mapping[storage_type] = storage_name
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Storage '{storage_name}' of type '{storage_type}' not found"
                )
        else:
            # Auto-select: find storages of this type
            available_storages = db.query(StorageConfig).filter_by(
                storage_type=storage_type,
                deleted_at=None,
                enabled=True
            ).all()
            
            if len(available_storages) == 1:
                # Single match - auto-select
                final_storage_mapping[storage_type] = available_storages[0].name
            elif len(available_storages) > 1:
                # Multiple matches - require user to specify
                raise HTTPException(
                    status_code=400,
                    detail=f"Multiple {storage_type} storages available. Please specify in storage_mapping: {[s.name for s in available_storages]}"
                )
            elif requirement.get("required", True):
                # Required but not found
                raise HTTPException(
                    status_code=400,
                    detail=f"Required storage type '{storage_type}' not found. Please create one in Settings."
                )
    
    # Update workflow config with template's workflow env vars
    if request.workflow_env:
        current_workflow_config = workflow.workflow_config or {}
        updated_workflow_config = {**current_workflow_config, **request.workflow_env}
        workflow.workflow_config = updated_workflow_config
        db.commit()

    # Create a new workflow from the template snapshot (replicate); node will reference this new workflow.
    from utils.workflow_from_template import create_workflow_from_template_data
    new_sub_workflow = create_workflow_from_template_data(
        db,
        template_data,
        workflow_name=f"Sub: {request.node_name}",
        workflow_config=request.workflow_env or {},
        template_id=request.template_id,
        attach_storage=True,
        storage_mapping=final_storage_mapping,
    )

    # Create node with node_type_id = "workflow_node" (special type for sub-workflows)
    node_config = {
        "template_id": request.template_id,
        "workflow_env": request.workflow_env or {},
        "storage_mapping": final_storage_mapping,
        "workflow_id": str(new_sub_workflow.id),
    }
    node = WorkflowNode(
        workflow_id=workspace_id,
        node_type_id="workflow_node",  # Special type for sub-workflows
        name=request.node_name,
        ui_x=0.0,  # Default position
        ui_y=0.0,
        config=node_config,
        node_config={},
    )
    
    db.add(node)
    db.commit()
    db.refresh(node)
    
    # Increment template usage count
    template.usage_count = (template.usage_count or 0) + 1
    db.commit()
    
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )


@router.post("/{workspace_id}/nodes/workflow-reference", response_model=NodeResponse, status_code=201)
async def create_workflow_reference_node(
    workspace_id: UUID,
    request: CreateWorkflowReferenceNodeRequest,
    db: Session = Depends(get_db),
):
    """Create a workflow node that references another workflow by ID (live reference). No template; edits in the linked workflow apply when this node runs."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ref_workflow_id = request.workflow_id
    if ref_workflow_id == workspace_id:
        raise HTTPException(status_code=400, detail="Cannot reference the same workflow")
    ref_workflow = db.query(Workflow).filter(
        Workflow.id == ref_workflow_id,
        Workflow.deleted_at.is_(None)
    ).first()
    if not ref_workflow:
        raise HTTPException(status_code=404, detail="Referenced workflow not found")

    from utils.template_helpers import detect_circular_dependency
    if detect_circular_dependency(str(workspace_id), str(ref_workflow_id), db=db):
        raise HTTPException(status_code=400, detail="Circular dependency detected")

    _validate_node_name(request.node_name)
    _check_name_uniqueness(db, workspace_id, request.node_name)

    node = WorkflowNode(
        workflow_id=workspace_id,
        node_type_id="workflow_node",
        name=request.node_name,
        ui_x=request.x,
        ui_y=request.y,
        config={"workflow_id": str(ref_workflow_id), "workflow_name": ref_workflow.name},
        node_config={},
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return NodeResponse(
        id=node.id,
        node_type_id=node.node_type_id,
        name=node.name,
        x=node.ui_x if node.ui_x is not None else 0.0,
        y=node.ui_y if node.ui_y is not None else 0.0,
        config=node.config,
        node_config=node.node_config or {},
        created_at=node.created_at
    )

