"""
Signal and wait state API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from database.connection import get_db
from database.models import RunHistory
from schemas.signal import (
    SignalRequest,
    ChannelSignalRequest,
    SignalResponse,
    WaitStateResponse,
)
from services.signals.channel_router import emit_to_channel, resolve_run_signal
from services.signals.wait_service import get_active_waits
from services.temporal.client import TemporalClient

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/signals/{channel}", response_model=SignalResponse)
async def emit_channel_signal(
    channel: str,
    body: ChannelSignalRequest,
    db: Session = Depends(get_db),
):
    """Emit a signal to all workflow runs waiting on the given channel."""
    try:
        temporal_client = await TemporalClient.get_client()
    except Exception as exc:
        logger.warning(f"Temporal not available, signal may not reach workflows: {exc}")
        temporal_client = None

    delivered = await emit_to_channel(
        channel=channel,
        signal=body.signal,
        data=body.data,
        db=db,
        temporal_client=temporal_client,
    )

    return SignalResponse(
        delivered_to=delivered,
        channel=channel,
        message=f"Signal '{body.signal}' delivered to {delivered} run(s) on channel '{channel}'",
    )


@router.post("/runs/{run_id}/signal", response_model=SignalResponse)
async def send_run_signal(
    run_id: UUID,
    body: SignalRequest,
    db: Session = Depends(get_db),
):
    """Send a point-to-point signal to a specific run that is in 'waiting' status."""
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "waiting":
        raise HTTPException(
            status_code=409,
            detail=f"Run is not in 'waiting' status (current status: {run.status})",
        )

    try:
        temporal_client = await TemporalClient.get_client()
    except Exception as exc:
        logger.warning(f"Temporal not available: {exc}")
        temporal_client = None

    resolved = await resolve_run_signal(
        run_id=str(run_id),
        signal=body.signal,
        data=body.data,
        db=db,
        temporal_client=temporal_client,
    )

    # Determine which channel was used
    active_waits = await get_active_waits(str(run_id), db)
    channel = active_waits[0].channel if active_waits else ""

    return SignalResponse(
        delivered_to=1 if resolved else 0,
        channel=channel,
        message=f"Signal '{body.signal}' {'delivered' if resolved else 'not delivered (no matching wait)'} for run {run_id}",
    )


@router.get("/runs/{run_id}/waits", response_model=List[WaitStateResponse])
async def get_run_waits(
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all active wait states for a run."""
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    waits = await get_active_waits(str(run_id), db)

    return [
        WaitStateResponse(
            id=str(w.id),
            run_id=str(w.run_id),
            node_id=w.node_id,
            channel=w.channel,
            mode=w.mode,
            signals_needed=w.signals_needed,
            signals_received=w.signals_received,
            timeout_at=w.timeout_at.isoformat() if w.timeout_at else None,
            satisfied=w.satisfied,
            created_at=w.created_at.isoformat() if w.created_at else "",
        )
        for w in waits
    ]
