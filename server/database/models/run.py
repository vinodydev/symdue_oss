"""
Run History model
"""
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from database.base import Base


class RunHistory(Base):
    """
    Execution run history for a workflow.
    Links to Temporal workflow for long-running executions.
    """
    __tablename__ = "run_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    parent_run_id = Column(UUID(as_uuid=True), ForeignKey("run_history.id"), nullable=True)
    
    # Temporal workflow ID
    temporal_workflow_id = Column(String(255), nullable=True)  # Link to Temporal workflow
    
    status = Column(String(20), nullable=False)  # 'success', 'error', 'cancelled', 'partial', 'running', 'paused', 'queued'
    duration = Column(Float, nullable=True)
    snapshot = Column(JSONB, nullable=False)
    
    label = Column(String(255), nullable=True)
    started_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    error_message = Column(Text, nullable=True)
    
    total_nodes = Column(Integer, nullable=True)
    completed_nodes = Column(Integer, nullable=True)
    failed_nodes = Column(Integer, nullable=True)
    skipped_nodes = Column(Integer, nullable=True)
    
    cancellation_requested_at = Column(TIMESTAMP, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="runs")

