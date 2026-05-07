# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Workspace (Workflow) API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import uuid
from database.connection import get_db
from database.models import Workflow, WorkflowNode, WorkflowEdge
from schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowDetail,
    WorkflowConfigUpdate,
    ExecutionConfigUpdate,
    WorkflowExport,
    WorkflowImport,
)
from schemas.node import NodeResponse
from schemas.edge import EdgeResponse
from schemas.node_type import CreateWorkflowFromTemplateRequest
from database.models import NodeType
from utils.template_helpers import detect_circular_dependency, serialize_node, serialize_edge

router = APIRouter()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workspace(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db)
):
    """Create a new workspace/workflow"""
    db_workflow = Workflow(name=workflow.name)
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow


@router.get("", response_model=List[WorkflowResponse])
async def list_workspaces(
    include_deleted: bool = False,
    db: Session = Depends(get_db)
):
    """List all workspaces"""
    query = db.query(Workflow)
    if not include_deleted:
        query = query.filter(Workflow.deleted_at.is_(None))
    return query.order_by(Workflow.updated_at.desc()).all()


@router.post("/import", response_model=WorkflowResponse, status_code=201)
async def import_workflow(
    payload: WorkflowImport,
    db: Session = Depends(get_db),
):
    """Create a new workflow from exported JSON. Generates new IDs for workflow, nodes, and edges."""
    # Validate node_type_id exists for all nodes
    node_ids_seen = set()
    for n in payload.nodes:
        if n.id in node_ids_seen:
            raise HTTPException(status_code=400, detail=f"Duplicate node id in export: {n.id}")
        node_ids_seen.add(n.id)
        nt = db.query(NodeType).filter_by(id=n.node_type_id).first()
        if not nt:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown node_type_id: {n.node_type_id}. Node type must exist in registry.",
            )
    node_id_set = set(n.id for n in payload.nodes)
    for e in payload.edges:
        if e.source_node_id not in node_id_set:
            raise HTTPException(
                status_code=400,
                detail=f"Edge references unknown source node: {e.source_node_id}",
            )
        if e.target_node_id not in node_id_set:
            raise HTTPException(
                status_code=400,
                detail=f"Edge references unknown target node: {e.target_node_id}",
            )
        if e.weight is not None and (e.weight < 0 or e.weight > 1):
            raise HTTPException(status_code=400, detail="Edge weight must be between 0 and 1")

    name = (payload.name or "").strip() or "Imported Workflow"
    transform = payload.transform if payload.transform is not None else {"x": 0, "y": 0, "k": 1}
    workflow_config = payload.workflow_config or {}

    workflow = Workflow(
        name=name,
        transform=transform,
        workflow_config=workflow_config,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    node_id_mapping = {}
    for serialized_node in payload.nodes:
        new_node = WorkflowNode(
            workflow_id=workflow.id,
            name=serialized_node.name,
            node_type_id=serialized_node.node_type_id,
            ui_x=serialized_node.ui_x,
            ui_y=serialized_node.ui_y,
            config=serialized_node.config,
            node_config=serialized_node.node_config,
        )
        db.add(new_node)
        db.flush()
        node_id_mapping[serialized_node.id] = str(new_node.id)

    for serialized_edge in payload.edges:
        new_source = node_id_mapping.get(serialized_edge.source_node_id)
        new_target = node_id_mapping.get(serialized_edge.target_node_id)
        if new_source and new_target:
            edge_kw = dict(
                workflow_id=workflow.id,
                source_node_id=new_source,
                target_node_id=new_target,
                weight=serialized_edge.weight,
            )
            if getattr(serialized_edge, "source_handle", None) is not None:
                edge_kw["source_handle"] = serialized_edge.source_handle
            edge = WorkflowEdge(**edge_kw)
            db.add(edge)

    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("/{workspace_id}", response_model=WorkflowDetail)
async def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a workspace by ID with nodes and edges"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get nodes and edges, mapping to response schemas
    nodes = db.query(WorkflowNode).filter(
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).all()
    
    edges = db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None)
    ).all()
    
    # Map to response schemas (handle None values for positions)
    node_responses = [
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
    
    edge_responses = [
        EdgeResponse(
            id=edge.id,
            source=edge.source_node_id,
            target=edge.target_node_id,
            weight=edge.weight,
            source_handle=getattr(edge, 'source_handle', None),
            created_at=edge.created_at
        )
        for edge in edges
    ]
    
    return WorkflowDetail(
        id=workflow.id,
        name=workflow.name,
        transform=workflow.transform,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        version=workflow.version,
        nodes=node_responses,
        edges=edge_responses
    )


@router.get("/{workspace_id}/export", response_model=WorkflowExport)
async def export_workflow(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    """Export workflow as JSON (nodes and edges with current IDs for round-trip)."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")

    nodes = db.query(WorkflowNode).filter(
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None),
    ).all()
    edges = db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None),
    ).all()

    return WorkflowExport(
        version=1,
        name=workflow.name,
        transform=workflow.transform or {"x": 0, "y": 0, "k": 1},
        workflow_config=workflow.workflow_config or {},
        nodes=[
            {
                "id": str(n.id),
                "name": n.name,
                "node_type_id": n.node_type_id,
                "ui_x": n.ui_x if n.ui_x is not None else 0.0,
                "ui_y": n.ui_y if n.ui_y is not None else 0.0,
                "config": n.config or {},
                "node_config": getattr(n, "node_config", None) or {},
            }
            for n in nodes
        ],
        edges=[
            {
                "source_node_id": str(e.source_node_id),
                "target_node_id": str(e.target_node_id),
                "weight": e.weight,
                **({"source_handle": e.source_handle} if getattr(e, "source_handle", None) is not None else {}),
            }
            for e in edges
        ],
    )


@router.patch("/{workspace_id}", response_model=WorkflowResponse)
async def update_workspace(
    workspace_id: UUID,
    workflow_update: WorkflowUpdate,
    db: Session = Depends(get_db)
):
    """Update a workspace"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if workflow_update.name is not None:
        workflow.name = workflow_update.name
        # Update workflow_name in any workflow reference node that points to this workflow
        ref_nodes = (
            db.query(WorkflowNode)
            .filter(
                WorkflowNode.node_type_id == "workflow_node",
                WorkflowNode.config["workflow_id"].astext == str(workspace_id),
            )
            .all()
        )
        for node in ref_nodes:
            cfg = dict(node.config or {})
            cfg["workflow_name"] = workflow.name
            node.config = cfg
    if workflow_update.transform is not None:
        workflow.transform = workflow_update.transform
    
    db.commit()
    db.refresh(workflow)
    return workflow


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete a workspace"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    from sqlalchemy.sql import func
    workflow.deleted_at = func.now()
    db.commit()
    return None


@router.post("/{workspace_id}/restore", response_model=WorkflowResponse)
async def restore_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """Restore a soft-deleted workspace"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.isnot(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Deleted workspace not found")
    
    workflow.deleted_at = None
    db.commit()
    db.refresh(workflow)
    return workflow


@router.put("/{workspace_id}/config")
async def update_workflow_config(
    workspace_id: UUID,
    config: WorkflowConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update workflow-level environment variables"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workflow.workflow_config = config.config
    db.commit()
    db.refresh(workflow)
    
    return {"workflow_id": str(workspace_id), "config": workflow.workflow_config}


@router.get("/{workspace_id}/config")
async def get_workflow_config(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """Get workflow-level environment variables"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return {"workflow_id": str(workspace_id), "config": workflow.workflow_config or {}}


@router.get("/{workspace_id}/execution-config")
async def get_execution_config(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    """Get per-workflow execution timeouts and limits."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "workflow_id": str(workspace_id),
        "execution_config": workflow.execution_config or {},
    }


@router.put("/{workspace_id}/execution-config")
async def update_execution_config(
    workspace_id: UUID,
    body: ExecutionConfigUpdate,
    db: Session = Depends(get_db),
):
    """Update per-workflow execution timeouts (partial update)."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None),
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    current = workflow.execution_config or {}
    if body.execution_config is not None:
        workflow.execution_config = {**current, **body.execution_config}
    db.commit()
    db.refresh(workflow)
    return {
        "workflow_id": str(workspace_id),
        "execution_config": workflow.execution_config or {},
    }


@router.get("/{workspace_id}/edge-nodes")
async def get_workflow_edge_nodes(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """List nodes that have 'Use input from parent' enabled (edge nodes). Key = node name or external_input_key. Used for Expected input keys and Run external input UI."""
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
    result = []
    for n in nodes:
        config = n.config or {}
        if not config.get("use_input_from_parent"):
            continue
        key = config.get("external_input_key") or n.name
        result.append({"node_id": str(n.id), "node_name": n.name, "key": key})
    return {"edge_nodes": result}


@router.post("/from-template")
async def create_workflow_from_template(
    request: CreateWorkflowFromTemplateRequest,
    db: Session = Depends(get_db)
):
    """Create workflow from template - configure environment variables and storage"""
    
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
    new_workflow_id = uuid.uuid4()
    if template.workflow_id:
        if detect_circular_dependency(str(new_workflow_id), str(template.workflow_id), db=db):
            raise HTTPException(status_code=400, detail="Circular dependency detected")
    
    # Get storage requirements
    storage_requirements = template_data.get("storage_requirements", {})
    
    # Create workflow
    workflow = Workflow(
        id=new_workflow_id,
        name=request.workflow_name,
        workflow_config=request.workflow_env or {},
        template_id=request.template_id,
    )
    db.add(workflow)
    db.commit()
    
    # Deserialize and create nodes
    serialized_nodes = template_data.get("nodes", [])
    serialized_edges = template_data.get("edges", [])
    
    node_id_mapping = {}  # old_id -> new_id
    
    for serialized_node in serialized_nodes:
        old_id = serialized_node["id"]
        new_node = WorkflowNode(
            workflow_id=workflow.id,
            name=serialized_node["name"],
            node_type_id=serialized_node["node_type_id"],
            ui_x=serialized_node.get("ui_x", 0.0),
            ui_y=serialized_node.get("ui_y", 0.0),
            config=serialized_node.get("config", {}),
            node_config=serialized_node.get("node_config", {}),
        )
        db.add(new_node)
        db.flush()  # Get the new ID
        node_id_mapping[old_id] = str(new_node.id)
    
    db.commit()
    
    # Attach storages automatically based on requirements
    from database.models import StorageConfig
    
    for storage_type, requirement in storage_requirements.items():
        # Find available storages of this type
        available_storages = db.query(StorageConfig).filter_by(
            storage_type=storage_type,
            deleted_at=None,
            enabled=True
        ).all()
        
        if len(available_storages) == 1:
            # Auto-attach to all nodes that need it
            storage = available_storages[0]
            storage_id = str(storage.id)
            
            # Find nodes that need this storage type
            for node in workflow.nodes:
                node_storage_configs = node.config.get("storage_configs", {})
                # Check if this node originally used this storage type
                # We'll attach it to all nodes for simplicity
                if not node_storage_configs:
                    node_storage_configs = {}
                
                # Add storage to node config
                alias = f"{storage_type}_storage"
                node_storage_configs[alias] = {
                    "storage_id": storage_id,
                    "storage_type": storage_type,
                }
                node.config["storage_configs"] = node_storage_configs
        elif len(available_storages) > 1:
            # Multiple storages - use first one (user can change later)
            storage = available_storages[0]
            storage_id = str(storage.id)
            
            for node in workflow.nodes:
                node_storage_configs = node.config.get("storage_configs", {})
                if not node_storage_configs:
                    node_storage_configs = {}
                
                alias = f"{storage_type}_storage"
                node_storage_configs[alias] = {
                    "storage_id": storage_id,
                    "storage_type": storage_type,
                }
                node.config["storage_configs"] = node_storage_configs
        # If no storage found and required, we'll continue anyway (user can add later)
    
    db.commit()
    
    # Create edges with new node IDs
    for serialized_edge in serialized_edges:
        old_source = serialized_edge["source_node_id"]
        old_target = serialized_edge["target_node_id"]
        
        new_source = node_id_mapping.get(old_source)
        new_target = node_id_mapping.get(old_target)
        
        if new_source and new_target:
            edge_kw = dict(
                workflow_id=workflow.id,
                source_node_id=new_source,
                target_node_id=new_target,
                weight=serialized_edge.get("weight", 1.0),
            )
            if serialized_edge.get("source_handle") is not None:
                edge_kw["source_handle"] = serialized_edge["source_handle"]
            edge = WorkflowEdge(**edge_kw)
            db.add(edge)
    
    db.commit()
    db.refresh(workflow)
    
    # Increment template usage count
    template.usage_count = (template.usage_count or 0) + 1
    db.commit()
    
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        transform=workflow.transform,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        version=workflow.version,
        workflow_config=workflow.workflow_config,
        template_id=workflow.template_id,
    )

