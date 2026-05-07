# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Workflow Node model
"""
from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from database.base import Base


class WorkflowNode(Base):
    """
    Node in a workflow graph
    """
    __tablename__ = "workflow_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    node_type_id = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    ui_x = Column(Float, nullable=False)
    ui_y = Column(Float, nullable=False)
    config = Column(JSONB, default={})
    
    # Node-level environment variables (node-specific, overrides workflow config)
    node_config = Column(JSONB, nullable=True, default={})
    # Example: {"NODE_TIMEOUT": "30", "NODE_RETRIES": "3"}
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    version = Column(Integer, default=1)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="nodes")
    source_edges = relationship(
        "WorkflowEdge",
        foreign_keys="WorkflowEdge.source_node_id",
        back_populates="source_node"
    )
    target_edges = relationship(
        "WorkflowEdge",
        foreign_keys="WorkflowEdge.target_node_id",
        back_populates="target_node"
    )

