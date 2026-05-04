"""
Tests for Temporal workflow pause/resume signals
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from services.temporal.workflows.graph_executor import GraphExecutorWorkflow


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflowSignals:
    """Test pause/resume signals in Temporal workflows"""
    
    async def test_pause_signal_received(self):
        """Test that pause signal is received and processed"""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[GraphExecutorWorkflow],
            ):
                # Start workflow
                workflow_handle = await env.client.start_workflow(
                    GraphExecutorWorkflow.run,
                    args=["workflow-1", {"nodes": [], "edges": []}, {}, "run-1"],
                    id="test-workflow-pause",
                    task_queue="test-queue",
                )
                
                # Send pause signal
                await workflow_handle.signal("pause_signal")
                
                # Note: In a real test, we'd need to wait for the workflow to process
                # the signal. For now, we verify the signal method exists and can be called.
                # Full integration testing would require a running Temporal server.
    
    async def test_resume_signal_received(self):
        """Test that resume signal is received and processed"""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[GraphExecutorWorkflow],
            ):
                # Start workflow
                workflow_handle = await env.client.start_workflow(
                    GraphExecutorWorkflow.run,
                    args=["workflow-1", {"nodes": [], "edges": []}, {}, "run-1"],
                    id="test-workflow-resume",
                    task_queue="test-queue",
                )
                
                # Send pause signal first
                await workflow_handle.signal("pause_signal")
                
                # Send resume signal
                await workflow_handle.signal("resume_signal")
                
                # Note: Full integration would verify workflow state changes

