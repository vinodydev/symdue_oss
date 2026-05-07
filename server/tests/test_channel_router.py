# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for channel_router functions.
"""
import pytest
import uuid
from unittest.mock import MagicMock, AsyncMock, patch


def _make_wait(channel="ch", mode="signal", signals_needed=None, run_id=None):
    from database.models.wait import WorkflowWait
    w = WorkflowWait()
    w.id = uuid.uuid4()
    w.run_id = uuid.uuid4() if run_id is None else uuid.UUID(run_id)
    w.node_id = "node1"
    w.channel = channel
    w.mode = mode
    w.signals_needed = signals_needed or []
    w.signals_received = []
    w.timeout_at = None
    w.satisfied = False
    return w


class TestEvaluateSignal:
    def test_signal_mode_matches(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="signal", signals_needed=["approved"])
        assert _evaluate_signal(wait, "approved", None) is True

    def test_signal_mode_no_match(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="signal", signals_needed=["approved"])
        assert _evaluate_signal(wait, "rejected", None) is False

    def test_signal_mode_empty_needed_matches_any(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="signal", signals_needed=[])
        assert _evaluate_signal(wait, "anything", None) is True

    def test_any_mode_first_match(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="any", signals_needed=["approved", "rejected"])
        assert _evaluate_signal(wait, "approved", None) is True

    def test_any_mode_no_match(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="any", signals_needed=["approved", "rejected"])
        assert _evaluate_signal(wait, "other", None) is False

    def test_all_mode_partial(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="all", signals_needed=["a", "b"])
        # First signal: not all received yet
        assert _evaluate_signal(wait, "a", None) is False
        assert "a" in wait.signals_received

    def test_all_mode_complete(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="all", signals_needed=["a", "b"])
        _evaluate_signal(wait, "a", None)
        result = _evaluate_signal(wait, "b", None)
        assert result is True

    def test_time_mode_always_false(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="time")
        assert _evaluate_signal(wait, "anything", None) is False

    def test_until_mode_always_false(self):
        from services.signals.channel_router import _evaluate_signal
        wait = _make_wait(mode="until")
        assert _evaluate_signal(wait, "anything", None) is False


@pytest.mark.asyncio
async def test_emit_to_channel_notifies_matching_waits():
    """emit_to_channel should call temporal_client for each satisfied wait."""
    from services.signals.channel_router import emit_to_channel

    wait = _make_wait(channel="approval", mode="signal", signals_needed=["approved"])

    db = MagicMock()
    temporal_client = MagicMock()
    temporal_client.send_receive_signal = AsyncMock(return_value=True)

    with patch("services.signals.channel_router.get_waits_for_channel", AsyncMock(return_value=[wait])), \
         patch("services.signals.channel_router.mark_wait_satisfied", AsyncMock()):
        count = await emit_to_channel("approval", "approved", None, db, temporal_client)

    assert count == 1
    temporal_client.send_receive_signal.assert_called_once()


@pytest.mark.asyncio
async def test_emit_to_channel_skips_non_matching():
    """emit_to_channel should not notify waits that don't match the signal."""
    from services.signals.channel_router import emit_to_channel

    wait = _make_wait(channel="approval", mode="signal", signals_needed=["approved"])

    db = MagicMock()
    temporal_client = MagicMock()
    temporal_client.send_receive_signal = AsyncMock(return_value=True)

    with patch("services.signals.channel_router.get_waits_for_channel", AsyncMock(return_value=[wait])), \
         patch("services.signals.channel_router.mark_wait_satisfied", AsyncMock()):
        count = await emit_to_channel("approval", "rejected", None, db, temporal_client)

    assert count == 0
    temporal_client.send_receive_signal.assert_not_called()


@pytest.mark.asyncio
async def test_emit_to_channel_empty_returns_zero():
    """emit_to_channel with no waiting runs should return 0."""
    from services.signals.channel_router import emit_to_channel

    db = MagicMock()
    temporal_client = MagicMock()

    with patch("services.signals.channel_router.get_waits_for_channel", AsyncMock(return_value=[])):
        count = await emit_to_channel("nonexistent", "signal", None, db, temporal_client)

    assert count == 0
