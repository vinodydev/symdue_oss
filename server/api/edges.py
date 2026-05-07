# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Edge API endpoints (with Weighted Intelligence)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from database.connection import get_db
from database.models import Workflow, WorkflowNode, WorkflowEdge
from schemas.edge import EdgeCreate, EdgeUpdate, EdgeResponse

router = APIRouter()


@router.post("/{workspace_id}/edges", response_model=EdgeResponse, status_code=201)
async def create_edge(
    workspace_id: UUID,
    edge: EdgeCreate,
    db: Session = Depends(get_db)
):
    """Create a new edge with weight (Weighted Intelligence)"""
    # Verify workspace exists
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Verify source and target nodes exist and belong to workspace
    source_node = db.query(WorkflowNode).filter(
        WorkflowNode.id == edge.source,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    target_node = db.query(WorkflowNode).filter(
        WorkflowNode.id == edge.target,
        WorkflowNode.workflow_id == workspace_id,
        WorkflowNode.deleted_at.is_(None)
    ).first()
    
    if not source_node:
        raise HTTPException(status_code=404, detail="Source node not found")
    if not target_node:
        raise HTTPException(status_code=404, detail="Target node not found")
    
    # Check if edge already exists
    existing = db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.source_node_id == edge.source,
        WorkflowEdge.target_node_id == edge.target,
        WorkflowEdge.deleted_at.is_(None)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Edge already exists")
    
    db_edge = WorkflowEdge(
        workflow_id=workspace_id,
        source_node_id=edge.source,
        target_node_id=edge.target,
        weight=edge.weight,
        source_handle=edge.source_handle,
    )
    db.add(db_edge)
    db.commit()
    db.refresh(db_edge)
    # Map source_node_id/target_node_id to source/target for response
    return EdgeResponse(
        id=db_edge.id,
        source=db_edge.source_node_id,
        target=db_edge.target_node_id,
        weight=db_edge.weight,
        source_handle=getattr(db_edge, 'source_handle', None),
        created_at=db_edge.created_at
    )


@router.get("/{workspace_id}/edges", response_model=List[EdgeResponse])
async def list_edges(
    workspace_id: UUID,
    db: Session = Depends(get_db)
):
    """List all edges in a workspace"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workspace_id,
        Workflow.deleted_at.is_(None)
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    edges = db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None)
    ).all()
    
    # Map source_node_id/target_node_id to source/target for response
    return [
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


@router.get("/{workspace_id}/edges/{edge_id}", response_model=EdgeResponse)
async def get_edge(
    workspace_id: UUID,
    edge_id: UUID,
    db: Session = Depends(get_db)
):
    """Get an edge by ID"""
    edge = db.query(WorkflowEdge).filter(
        WorkflowEdge.id == edge_id,
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None)
    ).first()
    
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    
    # Map source_node_id/target_node_id to source/target for response
    return EdgeResponse(
        id=edge.id,
        source=edge.source_node_id,
        target=edge.target_node_id,
        weight=edge.weight,
        source_handle=getattr(edge, 'source_handle', None),
        created_at=edge.created_at
    )


@router.patch("/{workspace_id}/edges/{edge_id}", response_model=EdgeResponse)
async def update_edge(
    workspace_id: UUID,
    edge_id: UUID,
    edge_update: EdgeUpdate,
    db: Session = Depends(get_db)
):
    """Update an edge's weight (Weighted Intelligence)"""
    edge = db.query(WorkflowEdge).filter(
        WorkflowEdge.id == edge_id,
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None)
    ).first()
    
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    
    if edge_update.weight is not None:
        edge.weight = edge_update.weight
    if edge_update.source_handle is not None:
        edge.source_handle = edge_update.source_handle
    db.commit()
    db.refresh(edge)
    return EdgeResponse(
        id=edge.id,
        source=edge.source_node_id,
        target=edge.target_node_id,
        weight=edge.weight,
        source_handle=getattr(edge, 'source_handle', None),
        created_at=edge.created_at
    )


@router.delete("/{workspace_id}/edges/{edge_id}", status_code=204)
async def delete_edge(
    workspace_id: UUID,
    edge_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete an edge"""
    edge = db.query(WorkflowEdge).filter(
        WorkflowEdge.id == edge_id,
        WorkflowEdge.workflow_id == workspace_id,
        WorkflowEdge.deleted_at.is_(None)
    ).first()
    
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    
    from sqlalchemy.sql import func
    edge.deleted_at = func.now()
    db.commit()
    return None

