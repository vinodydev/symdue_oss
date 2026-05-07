# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Create a Workflow from template_data (nodes + edges snapshot).
Used by: create-edit-copy, from-workflow-template (add workflow node), and create_workflow_from_template (workspaces).
"""
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import Workflow, WorkflowNode, WorkflowEdge, StorageConfig


def create_workflow_from_template_data(
    db: Session,
    template_data: Dict[str, Any],
    workflow_name: str,
    workflow_config: Optional[Dict[str, Any]] = None,
    template_id: Optional[str] = None,
    workflow_id: Optional[uuid.UUID] = None,
    attach_storage: bool = True,
    storage_mapping: Optional[Dict[str, str]] = None,
) -> Workflow:
    """
    Create a new workflow from serialized template_data (nodes, edges).
    Optionally attach storage based on storage_requirements and storage_mapping.

    Args:
        db: DB session
        template_data: dict with "nodes", "edges", "storage_requirements"
        workflow_name: name for the new workflow
        workflow_config: optional workflow_config for the new workflow
        template_id: optional template_id to set on the workflow
        workflow_id: optional UUID for the new workflow (default: new uuid)
        attach_storage: if True, attach storage instances to nodes
        storage_mapping: optional {storage_type: storage_name}; if not provided and attach_storage,
            auto-select single available storage per type

    Returns:
        The created Workflow (committed).
    """
    if workflow_id is None:
        workflow_id = uuid.uuid4()

    workflow = Workflow(
        id=workflow_id,
        name=workflow_name,
        workflow_config=workflow_config or {},
        template_id=template_id,
    )
    db.add(workflow)
    db.commit()

    serialized_nodes = template_data.get("nodes", [])
    serialized_edges = template_data.get("edges", [])
    node_id_mapping = {}

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
        db.flush()
        node_id_mapping[old_id] = str(new_node.id)

    db.commit()

    if attach_storage:
        storage_requirements = template_data.get("storage_requirements", {})
        resolved_mapping = storage_mapping or {}
        for storage_type in storage_requirements:
            if storage_type in resolved_mapping:
                storage_name = resolved_mapping[storage_type]
            else:
                available = db.query(StorageConfig).filter_by(
                    storage_type=storage_type,
                    deleted_at=None,
                    enabled=True,
                ).all()
                if len(available) == 1:
                    resolved_mapping[storage_type] = available[0].name
                elif len(available) > 1:
                    resolved_mapping[storage_type] = available[0].name
                else:
                    continue
            storage = db.query(StorageConfig).filter_by(
                name=resolved_mapping[storage_type],
                storage_type=storage_type,
                deleted_at=None,
                enabled=True,
            ).first()
            if not storage:
                continue
            storage_id = str(storage.id)
            for node in workflow.nodes:
                node_storage_configs = node.config.get("storage_configs", {}) or {}
                alias = f"{storage_type}_storage"
                node_storage_configs[alias] = {
                    "storage_id": storage_id,
                    "storage_type": storage_type,
                }
                node.config["storage_configs"] = node_storage_configs
        db.commit()

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
    return workflow
