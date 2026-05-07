# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Wait state persistence and retrieval.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.wait import WorkflowWait

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def persist_wait_state(
    run_id: str,
    node_id: str,
    channel: str,
    mode: str,
    signals_needed: List[str],
    timeout_at: Optional[datetime],
    db: Session,
) -> WorkflowWait:
    """
    Create or replace a WorkflowWait row for the given (run_id, node_id).
    Upserts by deleting existing row (if any) then inserting a new one.
    """
    # Delete any existing wait for this (run_id, node_id)
    existing = (
        db.query(WorkflowWait)
        .filter(
            WorkflowWait.run_id == UUID(run_id),
            WorkflowWait.node_id == node_id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    wait = WorkflowWait(
        run_id=UUID(run_id),
        node_id=node_id,
        channel=channel,
        mode=mode,
        signals_needed=signals_needed,
        signals_received=[],
        timeout_at=timeout_at,
        satisfied=False,
        satisfied_at=None,
    )
    db.add(wait)
    db.commit()
    db.refresh(wait)
    logger.info(
        f"[run={run_id}] Persisted wait for node={node_id} channel={channel} mode={mode}"
    )
    return wait


async def get_active_waits(run_id: str, db: Session) -> List[WorkflowWait]:
    """Return all unsatisfied waits for the given run."""
    return (
        db.query(WorkflowWait)
        .filter(
            WorkflowWait.run_id == UUID(run_id),
            WorkflowWait.satisfied == False,  # noqa: E712
        )
        .all()
    )


async def get_waits_for_channel(channel: str, db: Session) -> List[WorkflowWait]:
    """
    Return all unsatisfied, non-timed-out waits for the given channel.
    """
    now = _utcnow()
    query = (
        db.query(WorkflowWait)
        .filter(
            WorkflowWait.channel == channel,
            WorkflowWait.satisfied == False,  # noqa: E712
        )
    )
    results = query.all()
    # Filter out timed-out waits
    active = [
        w for w in results
        if w.timeout_at is None or w.timeout_at > now
    ]
    return active


async def mark_wait_satisfied(wait_id: str, db: Session) -> None:
    """Mark the given wait as satisfied."""
    wait = db.query(WorkflowWait).filter(WorkflowWait.id == UUID(wait_id)).first()
    if wait:
        wait.satisfied = True
        wait.satisfied_at = _utcnow()
        db.commit()


async def cleanup_run_waits(run_id: str, db: Session) -> None:
    """Delete or mark satisfied all waits for the given run (called on cancellation)."""
    waits = (
        db.query(WorkflowWait)
        .filter(WorkflowWait.run_id == UUID(run_id))
        .all()
    )
    for wait in waits:
        db.delete(wait)
    db.commit()
    logger.info(f"[run={run_id}] Cleaned up {len(waits)} wait(s)")
