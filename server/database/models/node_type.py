# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Node Type model
"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class NodeType(Base):
    """
    Node type that can represent:
    - Built-in types (python, llm, input, etc.)
    - Node templates (saved from individual nodes)
    - Workflow templates (saved from entire workflows)
    """
    __tablename__ = "node_types"
    
    id = Column(String(255), primary_key=True)
    category = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    
    # Type classification
    type_kind = Column(String(50), nullable=False, default="node_type")  # "node_type", "node_template", "workflow_template"
    
    # For node templates
    node_template_data = Column(JSONB, nullable=True)  # Full node config when saved as template
    
    # For workflow templates
    workflow_template_data = Column(JSONB, nullable=True)  # Full workflow (nodes + edges)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    
    # Environment variable configuration
    workflow_env_template = Column(JSONB, nullable=True)  # Required workflow-level env vars
    node_env_template = Column(JSONB, nullable=True)  # Required node-level env vars
    
    # Common fields
    default_config = Column(JSONB, nullable=True)
    config_schema = Column(JSONB, nullable=True)  # JSON Schema for env var configuration
    
    # Template metadata
    input_ports = Column(JSONB, nullable=True)  # For workflow templates: input node definitions
    output_ports = Column(JSONB, nullable=True)  # For workflow templates: output node definitions
    
    # Versioning
    version = Column(Integer, default=1)
    parent_template_id = Column(String(255), ForeignKey("node_types.id"), nullable=True)
    
    # Sharing and visibility
    is_builtin = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)  # Can be shared/used by others
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)
    usage_count = Column(Integer, default=0)  # How many times used

