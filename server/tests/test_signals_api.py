# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for the signals API endpoints.
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
    def test_emit_to_channel_no_waits_returns_zero(self, client):
        """POST /api/signals/{channel} with no waiting runs should return delivered_to=0."""
        with patch("services.temporal.client.TemporalClient.get_client", AsyncMock(return_value=MagicMock())), \
             patch("services.signals.channel_router.emit_to_channel", AsyncMock(return_value=0)):
            response = client.post(
                "/api/signals/test_channel",
                json={"signal": "approved", "data": {"key": "value"}},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["delivered_to"] == 0
        assert data["channel"] == "test_channel"


class TestSendRunSignal:
    def test_returns_404_when_run_not_found(self, client):
        """POST /api/runs/{run_id}/signal should return 404 when run doesn't exist."""
        fake_run_id = str(uuid.uuid4())
        response = client.post(
            f"/api/runs/{fake_run_id}/signal",
            json={"signal": "approved"},
        )
        assert response.status_code == 404

    def test_returns_409_when_run_not_waiting(self, client, test_db):
        """POST /api/runs/{run_id}/signal should return 409 when run is not in waiting status."""
        from database.models import Workflow, RunHistory

        # Create a workflow and run
        workflow = Workflow(name="Test Workflow", transform={"x": 0, "y": 0, "k": 1})
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


class TestGetRunWaits:
    def test_returns_empty_list_when_no_waits(self, client, test_db):
        """GET /api/runs/{run_id}/waits should return empty list when no waits exist."""
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

    def test_returns_404_when_run_not_found(self, client):
        """GET /api/runs/{run_id}/waits should return 404 when run doesn't exist."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/runs/{fake_id}/waits")
        assert response.status_code == 404
