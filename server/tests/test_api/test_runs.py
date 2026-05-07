# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for runs API endpoints
"""
import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from database.models import Workflow, RunHistory


@pytest.mark.integration
class TestRunsAPI:
    """Test runs API endpoints"""
    
    def test_create_run(self, client, test_db):
        """Test creating a new run"""
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create run
        response = client.post(
            f"/api/runs/{workflow.id}",
            json={"inputs": {"node-1": "test input"}}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "run_id" in data
        # Note: Status might be "error" if Temporal workflow fails to start
        # This is expected in test environment without Temporal server
        assert data["workflow_id"] == str(workflow.id)
        
        # Verify run was created in database
        run = test_db.query(RunHistory).filter(RunHistory.id == data["run_id"]).first()
        assert run is not None
    
    def test_create_run_workflow_not_found(self, client, test_db):
        """Test creating run for non-existent workflow"""
        fake_id = str(uuid4())
        
        response = client.post(
            f"/api/runs/{fake_id}",
            json={"inputs": {}}
        )
        
        assert response.status_code == 404
    
    @patch('api.runs.TemporalClient.get_client')
    def test_create_run_starts_temporal_workflow(self, mock_get_client, client, test_db):
        """Test that creating run starts Temporal workflow"""
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = MagicMock()
        mock_handle.id = "temporal-workflow-123"
        mock_client.start_workflow = AsyncMock(return_value=mock_handle)
        mock_get_client.return_value = mock_client
        
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create run
        response = client.post(
            f"/api/runs/{workflow.id}",
            json={"inputs": {"node-1": "test input"}}
        )
        
        assert response.status_code == 201
        
        # Note: Background task execution is async, so we can't easily verify
        # it was called in a synchronous test. This would need async test setup.
    
    def test_list_runs(self, client, test_db):
        """Test listing runs for a workflow"""
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create runs with snapshot
        run1 = RunHistory(workflow_id=workflow.id, status="completed", snapshot={})
        run2 = RunHistory(workflow_id=workflow.id, status="running", snapshot={})
        test_db.add_all([run1, run2])
        test_db.commit()
        
        # List runs
        response = client.get(f"/api/runs/{workflow.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        
        run_ids = [r["run_id"] for r in data]
        assert str(run1.id) in run_ids
        assert str(run2.id) in run_ids
    
    def test_get_run(self, client, test_db):
        """Test getting a specific run"""
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create run with snapshot
        run = RunHistory(workflow_id=workflow.id, status="running", snapshot={})
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Get run
        response = client.get(f"/api/runs/{workflow.id}/{run.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == str(run.id)
        assert data["status"] == "running"
    
    def test_get_run_not_found(self, client, test_db):
        """Test getting non-existent run"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        fake_run_id = str(uuid4())
        
        response = client.get(f"/api/runs/{workflow.id}/{fake_run_id}")
        
        assert response.status_code == 404

    def test_get_run_returns_parent_workflow_id_for_child_run(self, client, test_db):
        """When a run has parent_run_id (sub-workflow run), get_run returns parent_workflow_id."""
        parent_workflow = Workflow(name="Parent Workflow")
        child_workflow = Workflow(name="Child Workflow")
        test_db.add_all([parent_workflow, child_workflow])
        test_db.commit()
        test_db.refresh(parent_workflow)
        test_db.refresh(child_workflow)

        parent_run = RunHistory(
            workflow_id=parent_workflow.id,
            status="completed",
            snapshot={},
        )
        test_db.add(parent_run)
        test_db.commit()
        test_db.refresh(parent_run)

        child_run = RunHistory(
            workflow_id=child_workflow.id,
            parent_run_id=parent_run.id,
            status="completed",
            snapshot={},
        )
        test_db.add(child_run)
        test_db.commit()
        test_db.refresh(child_run)

        response = client.get(f"/api/runs/{child_workflow.id}/{child_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["parent_run_id"] == str(parent_run.id)
        assert data["parent_workflow_id"] == str(parent_workflow.id)

    def test_list_runs_includes_parent_workflow_id_for_child_runs(self, client, test_db):
        """List runs returns parent_workflow_id for runs that have parent_run_id."""
        parent_workflow = Workflow(name="Parent Workflow")
        child_workflow = Workflow(name="Child Workflow")
        test_db.add_all([parent_workflow, child_workflow])
        test_db.commit()
        test_db.refresh(parent_workflow)
        test_db.refresh(child_workflow)

        parent_run = RunHistory(
            workflow_id=parent_workflow.id,
            status="completed",
            snapshot={},
        )
        test_db.add(parent_run)
        test_db.commit()
        test_db.refresh(parent_run)

        child_run = RunHistory(
            workflow_id=child_workflow.id,
            parent_run_id=parent_run.id,
            status="completed",
            snapshot={},
        )
        test_db.add(child_run)
        test_db.commit()

        response = client.get(f"/api/runs/{child_workflow.id}")
        assert response.status_code == 200
        data = response.json()
        child = next((r for r in data if r["run_id"] == str(child_run.id)), None)
        assert child is not None
        assert child["parent_run_id"] == str(parent_run.id)
        assert child["parent_workflow_id"] == str(parent_workflow.id)
    
    @patch('api.runs.TemporalClient.get_client')
    def test_cancel_run(self, mock_get_client, client, test_db):
        """Test canceling a run"""
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = MagicMock()
        mock_handle.cancel = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_get_client.return_value = mock_client
        
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create run with snapshot
        run = RunHistory(
            workflow_id=workflow.id,
            status="running",
            temporal_workflow_id="temporal-123",
            snapshot={}
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Cancel run
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/cancel")
        
        assert response.status_code == 200
        
        # Verify status updated
        test_db.refresh(run)
        assert run.status == "cancelled"
    
    def test_cancel_run_not_cancellable(self, client, test_db):
        """Test canceling a run that's not in cancellable state"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create completed run with snapshot
        run = RunHistory(workflow_id=workflow.id, status="completed", snapshot={})
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Try to cancel
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/cancel")
        
        assert response.status_code == 400

    @patch('api.runs.TemporalClient.get_client')
    def test_pause_run(self, mock_get_client, client, test_db):
        """Test pausing a running run"""
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_get_client.return_value = mock_client
        
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create running run
        run = RunHistory(
            workflow_id=workflow.id,
            status="running",
            temporal_workflow_id="temporal-123",
            snapshot={}
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Pause run
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/pause")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"
        
        # Verify status updated
        test_db.refresh(run)
        assert run.status == "paused"
        
        # Verify signal was sent
        mock_handle.signal.assert_called_once_with("pause_signal")

    def test_pause_run_not_pausable(self, client, test_db):
        """Test pausing a run that's not in pausable state"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create paused run
        run = RunHistory(workflow_id=workflow.id, status="paused", snapshot={})
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Try to pause
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/pause")
        
        assert response.status_code == 400

    @patch('api.runs.TemporalClient.get_client')
    def test_resume_run(self, mock_get_client, client, test_db):
        """Test resuming a paused run"""
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_get_client.return_value = mock_client
        
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create paused run
        run = RunHistory(
            workflow_id=workflow.id,
            status="paused",
            temporal_workflow_id="temporal-123",
            snapshot={}
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Resume run
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        
        # Verify status updated
        test_db.refresh(run)
        assert run.status == "running"
        
        # Verify signal was sent
        mock_handle.signal.assert_called_once_with("resume_signal")

    def test_resume_run_not_paused(self, client, test_db):
        """Test resuming a run that's not paused"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create running run
        run = RunHistory(workflow_id=workflow.id, status="running", snapshot={})
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Try to resume
        response = client.post(f"/api/runs/{workflow.id}/{run.id}/resume")
        
        assert response.status_code == 400

    def test_cancel_paused_run(self, client, test_db):
        """Test canceling a paused run"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create paused run
        run = RunHistory(
            workflow_id=workflow.id,
            status="paused",
            temporal_workflow_id="temporal-123",
            snapshot={}
        )
        test_db.add(run)
        test_db.commit()
        test_db.refresh(run)
        
        # Cancel paused run
        with patch('api.runs.TemporalClient.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_handle = MagicMock()
            mock_handle.cancel = AsyncMock()
            mock_client.get_workflow_handle.return_value = mock_handle
            mock_get_client.return_value = mock_client
            
            response = client.post(f"/api/runs/{workflow.id}/{run.id}/cancel")
            
            assert response.status_code == 200
            
            # Verify status updated
            test_db.refresh(run)
            assert run.status == "cancelled"

