# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for wait_service — persistence, querying, and satisfaction of wait states.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


def _make_wait(run_id=None, node_id="node1", channel="test_channel", mode="signal",
               signals_needed=None, satisfied=False):
    from database.models.wait import WorkflowWait
    w = WorkflowWait()
    w.id = uuid.uuid4()
    w.run_id = uuid.UUID(run_id) if run_id else uuid.uuid4()
    w.node_id = node_id
    w.channel = channel
    w.mode = mode
    w.signals_needed = signals_needed or []
    w.signals_received = []
    w.timeout_at = None
    w.satisfied = satisfied
    w.satisfied_at = None
    w.created_at = datetime.utcnow()
    return w


@pytest.mark.asyncio
async def test_persist_wait_state():
    """persist_wait_state should add a WorkflowWait row and commit."""
    from services.signals.wait_service import persist_wait_state

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    run_id = str(uuid.uuid4())
    await persist_wait_state(
        run_id=run_id,
        node_id="node1",
        channel="approval",
        mode="signal",
        signals_needed=["approved"],
        timeout_at=None,
        db=db,
    )

    db.add.assert_called_once()
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_get_active_waits():
    """get_active_waits returns unsatisfied waits for the given run."""
    from services.signals.wait_service import get_active_waits

    run_id = str(uuid.uuid4())
    active_wait = _make_wait(run_id=run_id, satisfied=False)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [active_wait]

    result = await get_active_waits(run_id, db)
    assert len(result) == 1
    assert result[0].satisfied is False


@pytest.mark.asyncio
async def test_mark_wait_satisfied():
    """mark_wait_satisfied sets satisfied=True and satisfied_at."""
    from services.signals.wait_service import mark_wait_satisfied

    wait = _make_wait()
    wait_id = str(wait.id)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = wait

    await mark_wait_satisfied(wait_id, db)

    assert wait.satisfied is True
    assert wait.satisfied_at is not None
    db.commit.assert_called()


def test_channel_evaluation_signal_mode():
    """_evaluate_signal: signal mode matches correct signal, rejects others."""
    from services.signals.channel_router import _evaluate_signal

    wait = _make_wait(mode="signal", signals_needed=["approved"])
    assert _evaluate_signal(wait, "approved", None) is True
    assert _evaluate_signal(wait, "rejected", None) is False


def test_channel_evaluation_any_mode():
    """_evaluate_signal: any mode matches any listed signal."""
    from services.signals.channel_router import _evaluate_signal

    wait = _make_wait(mode="any", signals_needed=["approved", "rejected"])
    assert _evaluate_signal(wait, "approved", None) is True
    assert _evaluate_signal(wait, "rejected", None) is True
    assert _evaluate_signal(wait, "other", None) is False
