# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Workflow (Workspace) model
"""
from sqlalchemy import Column, String, Integer, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from database.base import Base


class Workflow(Base):
    """
    Workflow (Workspace) - represents a visual graph/workflow
    """
    __tablename__ = "workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    transform = Column(JSONB, default={"x": 0, "y": 0, "k": 1})
    
    # Cache
    graph_snapshot = Column(JSONB, nullable=True)
    graph_snapshot_version = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # Versioning
    version = Column(Integer, default=1)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    
    # Workflow-level environment variables (shared by all nodes)
    workflow_config = Column(JSONB, nullable=True, default={})
    # Example: {"S3_BUCKET": "my-bucket", "DATABASE_URL": "postgresql://..."}

    # Per-workflow execution timeouts (graph and node limits)
    execution_config = Column(JSONB, nullable=True, default={})
    # Example: {"graph_activity_timeout_minutes": 60, "heartbeat_timeout_minutes": 5,
    #           "default_node_timeout_seconds": 600, "max_node_timeout_seconds": 3600}

    # Template reference (if created from a workflow template)
    template_id = Column(String(255), ForeignKey("node_types.id"), nullable=True)
    
    # Relationships
    nodes = relationship("WorkflowNode", back_populates="workflow", cascade="all, delete-orphan")
    edges = relationship("WorkflowEdge", back_populates="workflow", cascade="all, delete-orphan")
    runs = relationship("RunHistory", back_populates="workflow")

