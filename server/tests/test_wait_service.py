"""
Tests for wait_service functions.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


def _make_mock_db():
    """Create a simple mock DB session."""
    db = MagicMock()
    return db


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
async def test_persist_wait_state_creates_row():
    """persist_wait_state should add a WorkflowWait row and commit."""
    from services.signals.wait_service import persist_wait_state

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no existing

    run_id = str(uuid.uuid4())
    wait = await persist_wait_state(
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
async def test_persist_wait_state_upserts():
    """persist_wait_state should delete the existing row before inserting."""
    from services.signals.wait_service import persist_wait_state

    run_id = str(uuid.uuid4())
    existing = _make_wait(run_id=run_id, node_id="node1")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    await persist_wait_state(
        run_id=run_id,
        node_id="node1",
        channel="approval",
        mode="signal",
        signals_needed=["approved"],
        timeout_at=None,
        db=db,
    )

    db.delete.assert_called_once_with(existing)
    db.flush.assert_called()


@pytest.mark.asyncio
async def test_get_active_waits_filters_satisfied():
    """get_active_waits should return only unsatisfied waits for the run."""
    from services.signals.wait_service import get_active_waits

    run_id = str(uuid.uuid4())
    active_wait = _make_wait(run_id=run_id, satisfied=False)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [active_wait]

    result = await get_active_waits(run_id, db)
    assert len(result) == 1
    assert result[0].satisfied is False


@pytest.mark.asyncio
async def test_get_waits_for_channel_filters_timed_out():
    """get_waits_for_channel should exclude waits past their timeout_at."""
    from services.signals.wait_service import get_waits_for_channel

    active_wait = _make_wait(channel="ch1")
    timed_out_wait = _make_wait(channel="ch1")
    # Set timeout_at to the past
    timed_out_wait.timeout_at = datetime.utcnow() - timedelta(hours=1)
    active_wait.timeout_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [active_wait, timed_out_wait]

    result = await get_waits_for_channel("ch1", db)
    assert len(result) == 1
    assert result[0].timeout_at is None


@pytest.mark.asyncio
async def test_mark_wait_satisfied_sets_fields():
    """mark_wait_satisfied should set satisfied=True and satisfied_at."""
    from services.signals.wait_service import mark_wait_satisfied

    wait = _make_wait()
    wait_id = str(wait.id)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = wait

    await mark_wait_satisfied(wait_id, db)

    assert wait.satisfied is True
    assert wait.satisfied_at is not None
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_cleanup_run_waits_deletes_all():
    """cleanup_run_waits should delete all waits for the given run."""
    from services.signals.wait_service import cleanup_run_waits

    run_id = str(uuid.uuid4())
    w1 = _make_wait(run_id=run_id)
    w2 = _make_wait(run_id=run_id)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [w1, w2]

    await cleanup_run_waits(run_id, db)

    assert db.delete.call_count == 2
    db.commit.assert_called()
