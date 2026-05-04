"""
Run schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID


class RunCreate(BaseModel):
    """Schema for creating a new run"""
    inputs: Dict[str, Any] = {}
    label: Optional[str] = None
    # When provided, merged with inputs and passed to execution (for edge nodes when running standalone)
    external_input: Optional[Dict[str, Any]] = None


class ResumeRunCreate(BaseModel):
    """Schema for creating a new run that resumes from a previous run (checkpoint)."""
    from_run_id: UUID
    inputs: Optional[Dict[str, Any]] = None  # If omitted, use snapshot.inputs from from_run_id
    start_from_node_id: Optional[str] = None  # If set, re-run from this node onward


class RunResponse(BaseModel):
    """Schema for run response"""
    run_id: UUID
    status: str
    workflow_id: UUID
    temporal_workflow_id: Optional[str] = None
    parent_run_id: Optional[UUID] = None
    parent_workflow_id: Optional[UUID] = None  # When parent_run_id is set, workflow that owns the parent run
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    snapshot: Optional[Dict[str, Any]] = None
