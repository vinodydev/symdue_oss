"""
Tests for signals API endpoints: channel emit and run-level signal delivery.
"""
import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_temporal():
    mock = MagicMock()
    mock.send_receive_signal = AsyncMock(return_value=True)
    return mock


class TestEmitChannelSignal:
    def test_emit_to_channel_no_waiters(self, client):
        """POST /api/signals/{channel} with no runs waiting returns delivered_to=0."""
        with patch("services.temporal.client.TemporalClient.get_client", AsyncMock(return_value=MagicMock())), \
             patch("services.signals.channel_router.emit_to_channel", AsyncMock(return_value=0)):
            response = client.post(
                "/api/signals/testchannel",
                json={"signal": "test", "data": None},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["delivered_to"] == 0
        assert data["channel"] == "testchannel"


class TestGetRunWaits:
    def test_get_run_waits_empty(self, client, test_db):
        """GET /api/runs/{run_id}/waits for a run with no waits returns empty list."""
        from database.models import Workflow, RunHistory

        workflow = Workflow(name="Test Workflow", transform={"x": 0, "y": 0, "k": 1})
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)

        run = RunHistory(
            workflow_id=workflow.id,
            status="waiting",
            snapshot={},
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)

        response = client.get(f"/api/runs/{run.id}/waits")
        assert response.status_code == 200
        assert response.json() == []


class TestSendRunSignal:
    def test_send_signal_to_non_waiting_run(self, client, test_db):
        """POST /api/runs/{run_id}/signal when run status is 'running' returns 409."""
        from database.models import Workflow, RunHistory

        workflow = Workflow(name="Signal Test Workflow", transform={"x": 0, "y": 0, "k": 1})
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)

        run = RunHistory(
            workflow_id=workflow.id,
            status="running",  # Not "waiting"
            snapshot={},
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)

        response = client.post(
            f"/api/runs/{run.id}/signal",
            json={"signal": "approved"},
        )
        assert response.status_code == 409
        assert "waiting" in response.json()["detail"].lower()
