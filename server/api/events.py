# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Events management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from database.connection import get_db
from database.models.event import Event
from database.models.event_invocation import EventInvocation
from schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventInvocationResponse,
    EventInvocationDetail,
)
from api.event_runner import run_event_script
from config.settings import get_settings

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


_GATE_DETAIL = (
    "Event scripts are disabled in this build. "
    "For scheduled / queue / webhook triggers, see docs/scheduling.md. "
    "To enable the feature anyway, set EVENT_SCRIPTS_ENABLED=true (see SECURITY.md for the risk model)."
)


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse(
        id=str(event.id),
        name=event.name,
        type=event.type,
        schedule=event.schedule,
        script=event.script or "",
        state=event.state,
        enabled=event.enabled,
        queue_name=event.queue_name,
        webhook_secret=event.webhook_secret,
        last_run_at=event.last_run_at.isoformat() if event.last_run_at else None,
        next_run_at=event.next_run_at.isoformat() if event.next_run_at else None,
        created_at=event.created_at.isoformat() if event.created_at else "",
        updated_at=event.updated_at.isoformat() if event.updated_at else "",
    )


def _invocation_to_response(inv: EventInvocation) -> EventInvocationResponse:
    return EventInvocationResponse(
        id=str(inv.id),
        event_id=str(inv.event_id),
        triggered_by=inv.triggered_by,
        input=inv.input,
        state_before=inv.state_before,
        state_after=inv.state_after,
        runtime_calls=inv.runtime_calls,
        error=inv.error,
        duration_ms=inv.duration_ms,
        started_at=inv.started_at.isoformat() if inv.started_at else "",
        completed_at=inv.completed_at.isoformat() if inv.completed_at else None,
    )


def _invocation_to_detail(inv: EventInvocation) -> EventInvocationDetail:
    return EventInvocationDetail(
        id=str(inv.id),
        event_id=str(inv.event_id),
        triggered_by=inv.triggered_by,
        input=inv.input,
        state_before=inv.state_before,
        state_after=inv.state_after,
        runtime_calls=inv.runtime_calls,
        error=inv.error,
        duration_ms=inv.duration_ms,
        started_at=inv.started_at.isoformat() if inv.started_at else "",
        completed_at=inv.completed_at.isoformat() if inv.completed_at else None,
        log_output=inv.log_output,
        traceback=inv.traceback,
    )


# ── Event CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=List[EventResponse])
async def list_events(db: Session = Depends(get_db)):
    """List all events."""
    events = db.query(Event).order_by(Event.created_at.desc()).all()
    return [_event_to_response(e) for e in events]


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(body: EventCreate, db: Session = Depends(get_db)):
    """Create a new event.

    When EVENT_SCRIPTS_ENABLED is False (default in OSS), a non-empty `script`
    is rejected with 403 — the body still describes a valid Event row, but the
    runtime would refuse to execute it anyway, so we fail early at write-time.
    """
    if body.script and not get_settings().event_scripts_enabled:
        raise HTTPException(status_code=403, detail=_GATE_DETAIL)
    event = Event(
        name=body.name,
        type=body.type,
        schedule=body.schedule,
        script=body.script,
        state=body.state or {},
        enabled=body.enabled,
        queue_name=body.queue_name,
        webhook_secret=body.webhook_secret,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_to_response(event)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, db: Session = Depends(get_db)):
    """Get a single event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(event_id: UUID, body: EventUpdate, db: Session = Depends(get_db)):
    """Update an event (partial update)."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = body.model_dump(exclude_unset=True)
    if updates.get("script") and not get_settings().event_scripts_enabled:
        raise HTTPException(status_code=403, detail=_GATE_DETAIL)
    for field, value in updates.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return _event_to_response(event)


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: UUID, db: Session = Depends(get_db)):
    """Delete an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()


@router.post("/{event_id}/enable", response_model=EventResponse)
async def enable_event(event_id: UUID, db: Session = Depends(get_db)):
    """Enable an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.enabled = True
    db.commit()
    db.refresh(event)
    return _event_to_response(event)


@router.post("/{event_id}/disable", response_model=EventResponse)
async def disable_event(event_id: UUID, db: Session = Depends(get_db)):
    """Disable an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.enabled = False
    db.commit()
    db.refresh(event)
    return _event_to_response(event)


@router.post("/{event_id}/trigger", response_model=EventInvocationDetail)
async def trigger_event(
    event_id: UUID,
    body: dict = None,
    db: Session = Depends(get_db),
):
    """Trigger an event immediately with an optional JSON body as input."""
    if not get_settings().event_scripts_enabled:
        raise HTTPException(status_code=503, detail=_GATE_DETAIL)
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    invocation = await run_event_script(
        event=event,
        triggered_by="manual",
        input_data=body,
        db=db,
    )
    return _invocation_to_detail(invocation)


# ── Invocations ─────────────────────────────────────────────────────────────

@router.get("/{event_id}/invocations", response_model=List[EventInvocationResponse])
async def list_invocations(
    event_id: UUID,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List invocations for an event (paginated, no log_output/traceback)."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    invocations = (
        db.query(EventInvocation)
        .filter(EventInvocation.event_id == event_id)
        .order_by(EventInvocation.started_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [_invocation_to_response(inv) for inv in invocations]


@router.get("/{event_id}/invocations/{invocation_id}", response_model=EventInvocationDetail)
async def get_invocation(
    event_id: UUID,
    invocation_id: UUID,
    db: Session = Depends(get_db),
):
    """Get full detail for a single event invocation."""
    inv = (
        db.query(EventInvocation)
        .filter(
            EventInvocation.id == invocation_id,
            EventInvocation.event_id == event_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invocation not found")
    return _invocation_to_detail(inv)
