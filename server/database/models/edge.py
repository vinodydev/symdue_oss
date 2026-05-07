# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Workflow Edge model
"""
from sqlalchemy import Column, Float, ForeignKey, CheckConstraint, String
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from database.base import Base


class WorkflowEdge(Base):
    """
    Edge connecting two nodes in a workflow graph.
    Includes weight (0.0-1.0) for Weighted Intelligence feature.
    """
    __tablename__ = "workflow_edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("workflow_nodes.id"), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("workflow_nodes.id"), nullable=False)
    weight = Column(Float, default=1.0)  # KEY FEATURE: Weighted Intelligence (0.0-1.0)
    source_handle = Column(String(20), nullable=True)  # "true" | "false" for condition-node branches
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('weight >= 0.0 AND weight <= 1.0', name='check_weight_range'),
    )
    
    # Relationships
    workflow = relationship("Workflow", back_populates="edges")
    source_node = relationship(
        "WorkflowNode",
        foreign_keys=[source_node_id],
        back_populates="source_edges"
    )
    target_node = relationship(
        "WorkflowNode",
        foreign_keys=[target_node_id],
        back_populates="target_edges"
    )

