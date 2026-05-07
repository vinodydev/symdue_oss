# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Graph builder - Builds graph JSON structure from database
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from database.models import Workflow, WorkflowNode, WorkflowEdge
from uuid import UUID

logger = logging.getLogger(__name__)


def build_graph_json(workflow_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Build graph JSON structure from database records.
    
    This converts normalized database structure (nodes + edges tables)
    into a JSON structure suitable for LangGraph compilation.
    
    Edges referencing deleted / non-existent nodes are automatically
    filtered out (defense in depth against stale edges).
    
    Args:
        workflow_id: Workflow/workspace ID
        db: Database session
    
    Returns:
        {
            "nodes": [
                {
                    "id": "uuid",
                    "name": "my_node",
                    "node_type_id": "custom-python",
                    "config": {...}
                },
                ...
            ],
            "edges": [
                {
                    "source": "node-uuid",
                    "target": "node-uuid",
                    "weight": 0.8
                },
                ...
            ]
        }
    """
    # Query active nodes
    nodes = db.query(WorkflowNode).filter(
        WorkflowNode.workflow_id == workflow_id,
        WorkflowNode.deleted_at.is_(None)
    ).all()
    
    # Query active edges
    edges = db.query(WorkflowEdge).filter(
        WorkflowEdge.workflow_id == workflow_id,
        WorkflowEdge.deleted_at.is_(None)
    ).all()
    
    # Build nodes array
    nodes_json = [
        {
            "id": str(node.id),
            "name": node.name,
            "node_type_id": node.node_type_id,
            "config": node.config or {}
        }
        for node in nodes
    ]
    
    # Build set of valid node IDs for edge validation
    valid_node_ids = {str(node.id) for node in nodes}
    
    # Build edges array — filter out stale edges referencing deleted nodes
    edges_json = []
    for edge in edges:
        src = str(edge.source_node_id)
        tgt = str(edge.target_node_id)
        if src in valid_node_ids and tgt in valid_node_ids:
            edge_entry = {
                "source": src,
                "target": tgt,
                "weight": float(edge.weight)
            }
            if getattr(edge, "source_handle", None) is not None:
                edge_entry["source_handle"] = edge.source_handle
            edges_json.append(edge_entry)
        else:
            logger.warning(
                f"Skipping stale edge {edge.id}: "
                f"source={src[:8]} (exists={src in valid_node_ids}), "
                f"target={tgt[:8]} (exists={tgt in valid_node_ids})"
            )
    
    return {
        "nodes": nodes_json,
        "edges": edges_json
    }

