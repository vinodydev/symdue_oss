# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Event schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class EventCreate(BaseModel):
    """Schema for creating a new event"""
    name: str
    type: str
    schedule: Optional[str] = None
    script: str = ""
    state: Optional[Dict[str, Any]] = None
    enabled: bool = True
    queue_name: Optional[str] = None
    webhook_secret: Optional[str] = None


class EventUpdate(BaseModel):
    """Schema for updating an event (all fields optional)"""
    name: Optional[str] = None
    type: Optional[str] = None
    schedule: Optional[str] = None
    script: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    queue_name: Optional[str] = None
    webhook_secret: Optional[str] = None


class EventResponse(BaseModel):
    """Schema for event response"""
    id: str
    name: str
    type: str
    schedule: Optional[str] = None
    script: str
    state: Optional[Dict[str, Any]] = None
    enabled: bool
    queue_name: Optional[str] = None
    webhook_secret: Optional[str] = None
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str
    updated_at: str


class EventInvocationResponse(BaseModel):
    """Schema for event invocation list view (no log_output or traceback)"""
    id: str
    event_id: str
    triggered_by: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
    runtime_calls: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None


class EventInvocationDetail(EventInvocationResponse):
    """Schema for event invocation detail view (includes full log_output and traceback)"""
    log_output: Optional[str] = None
    traceback: Optional[str] = None
