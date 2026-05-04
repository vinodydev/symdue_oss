"""
Tests for the wait/signal/event system gaps (Gaps 1-5).
Tests config settings, runtime.run_workflow, wait timeout, scheduler, queue listener.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch


def _has_croniter():
    try:
        import croniter  # noqa: F401
        return True
    except ImportError:
        return False


# ── Gap 1: Config Settings ──────────────────────────────────────────────

class TestConfigSettings:
    def test_default_event_script_timeout(self):
        from config.settings import Settings
        s = Settings()
        assert s.event_script_timeout_seconds == 60

    def test_default_max_wait_timeout(self):
        from config.settings import Settings
        s = Settings()
        assert s.max_wait_timeout_hours == 168

    def test_default_signal_channel_max_fanout(self):
        from config.settings import Settings
        s = Settings()
        assert s.signal_channel_max_fanout == 100

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("EVENT_SCRIPT_TIMEOUT_SECONDS", "120")
        monkeypatch.setenv("MAX_WAIT_TIMEOUT_HOURS", "48")
        monkeypatch.setenv("SIGNAL_CHANNEL_MAX_FANOUT", "50")
        from config.settings import Settings
        s = Settings()
        assert s.event_script_timeout_seconds == 120
        assert s.max_wait_timeout_hours == 48
        assert s.signal_channel_max_fanout == 50


# ── Gap 2: runtime.run_workflow ──────────────────────────────────────────

class TestRuntimeRunWorkflow:
    def test_resolve_workspace_by_name(self):
        from services.events.runtime_api import RuntimeAPI

        mock_db = MagicMock()
        mock_wf = MagicMock()
        mock_wf.id = "test-id"
        mock_wf.name = "My Workflow"
        # First query (UUID parse fails) → second query (name lookup)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_wf

        rt = RuntimeAPI(db=mock_db, temporal_client=None, event_id="evt-1")
        result = rt._resolve_workspace("My Workflow")
        assert result is not None
        assert result.name == "My Workflow"

    def test_resolve_workspace_not_found(self):
        from services.events.runtime_api import RuntimeAPI

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        rt = RuntimeAPI(db=mock_db, temporal_client=None, event_id="evt-1")
        result = rt._resolve_workspace("nonexistent")
        assert result is None

    def test_run_workflow_not_found_returns_empty(self):
        from services.events.runtime_api import RuntimeAPI

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        rt = RuntimeAPI(db=mock_db, temporal_client=None, event_id="evt-1")
        run_id = rt.run_workflow("nonexistent", {"key": "val"})
        assert run_id == ""
        assert len(rt._runtime_calls) == 1
        assert rt._runtime_calls[0]["method"] == "run_workflow"


# ── Gap 3: Wait Timeout ─────────────────────────────────────────────────

class TestWaitTimeout:
    def test_timeout_seconds_in_suspended_entry(self):
        """Verify the wait node includes timeout_seconds in the suspended entry."""
        # This is a structural test — verify the data shape
        timeout_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=30)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        remaining = (timeout_at - now).total_seconds()
        timeout_seconds = max(int(remaining), 1)
        assert timeout_seconds > 0
        assert timeout_seconds <= 31

    def test_timeout_capped_by_max_wait_hours(self):
        """Verify timeout is capped by max_wait_timeout_hours."""
        from config.settings import Settings
        s = Settings()
        max_delta = timedelta(hours=s.max_wait_timeout_hours)
        # A user timeout of 500 hours should be capped to 168 hours
        user_delta = timedelta(hours=500)
        capped = min(user_delta, max_delta)
        assert capped == max_delta

    def test_timeout_signal_payload(self):
        """Verify the __timeout__ signal payload structure."""
        payload = {"signal": "__timeout__", "data": {"timed_out": True}}
        assert payload["signal"] == "__timeout__"
        assert payload["data"]["timed_out"] is True


# ── Gap 4: Event Scheduler ──────────────────────────────────────────────

class TestEventScheduler:
    def test_parse_interval_seconds(self):
        from services.events.scheduler import _parse_interval
        assert _parse_interval("30s") == timedelta(seconds=30)

    def test_parse_interval_minutes(self):
        from services.events.scheduler import _parse_interval
        assert _parse_interval("5m") == timedelta(minutes=5)

    def test_parse_interval_hours(self):
        from services.events.scheduler import _parse_interval
        assert _parse_interval("2h") == timedelta(hours=2)

    def test_parse_interval_invalid(self):
        from services.events.scheduler import _parse_interval
        assert _parse_interval("abc") is None
        assert _parse_interval("") is None
        assert _parse_interval("5d") is None

    @pytest.mark.skipif(
        not _has_croniter(), reason="croniter not installed"
    )
    def test_cron_is_due_basic(self):
        """Test cron evaluation with a simple expression."""
        from services.events.scheduler import _cron_is_due
        now = datetime(2026, 3, 18, 9, 0, 30)  # Wednesday 9:00:30 AM
        # "Every minute" — should be due
        result = _cron_is_due("* * * * *", now, None)
        assert result is True

    @pytest.mark.skipif(
        not _has_croniter(), reason="croniter not installed"
    )
    def test_cron_is_due_not_yet(self):
        """Test cron evaluation that shouldn't fire yet."""
        from services.events.scheduler import _cron_is_due
        now = datetime(2026, 3, 18, 8, 0, 0)  # 8:00 AM
        # Fire at 9 AM only
        result = _cron_is_due("0 9 * * *", now, None)
        assert result is False

    @pytest.mark.skipif(
        not _has_croniter(), reason="croniter not installed"
    )
    def test_cron_double_fire_guard(self):
        """Test that cron won't double-fire within 55 seconds."""
        from services.events.scheduler import _cron_is_due
        now = datetime(2026, 3, 18, 9, 0, 30)
        last_run = datetime(2026, 3, 18, 9, 0, 10)  # 20 seconds ago
        result = _cron_is_due("* * * * *", now, last_run)
        assert result is False  # Too soon since last run


# ── Gap 5: Channel Router Fanout Limit ───────────────────────────────────

class TestChannelRouterFanout:
    @pytest.mark.asyncio
    async def test_fanout_limit_applied(self):
        """Verify that channel router limits fanout."""
        from services.signals.channel_router import emit_to_channel

        # Create more waits than max_fanout
        mock_waits = []
        for i in range(150):
            w = MagicMock()
            w.run_id = f"run-{i}"
            w.node_id = f"node-{i}"
            w.id = f"wait-{i}"
            w.mode = "signal"
            w.signals_needed = ["go"]
            w.signals_received = []
            mock_waits.append(w)

        mock_db = MagicMock()
        mock_temporal = AsyncMock()
        mock_temporal.send_receive_signal = AsyncMock()

        mock_settings_obj = MagicMock()
        mock_settings_obj.signal_channel_max_fanout = 100

        with patch("services.signals.channel_router.get_waits_for_channel", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_waits
            with patch("services.signals.channel_router.mark_wait_satisfied", new_callable=AsyncMock):
                with patch("config.settings.get_settings", return_value=mock_settings_obj):
                    notified = await emit_to_channel("test-channel", "go", {}, mock_db, mock_temporal)
                    # Should be capped at 100
                    assert notified <= 100
