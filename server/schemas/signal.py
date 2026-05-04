"""
Signal schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class SignalRequest(BaseModel):
    """Schema for sending a signal to a specific run"""
    signal: str
    data: Optional[Dict[str, Any]] = None


class ChannelSignalRequest(BaseModel):
    """Schema for broadcasting a signal to a named channel"""
    signal: str
    data: Optional[Dict[str, Any]] = None


class SignalResponse(BaseModel):
    """Response after emitting a signal"""
    delivered_to: int
    channel: str
    message: str


class WaitStateResponse(BaseModel):
    """Schema representing an active wait state for a run"""
    id: str
    run_id: str
    node_id: str
    channel: str
    mode: str
    signals_needed: Optional[List[str]] = None
    signals_received: Optional[List[str]] = None
    timeout_at: Optional[str] = None
    satisfied: bool
    created_at: str
