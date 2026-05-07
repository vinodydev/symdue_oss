# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for Temporal activities (mocked)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.temporal.activities.node_executor import (
    execute_input_node_activity,
    execute_python_node_activity,
    execute_llm_node_activity,
    execute_memory_node_activity,
    save_run_results_activity,
    publish_workflow_status_activity
)


@pytest.mark.unit
class TestNodeActivities:
    """Test node executor activities"""
    
    @pytest.mark.asyncio
    async def test_execute_input_node(self):
        """Test input node execution"""
        node_id = "node-1"
        config = {"value": "test input"}
        inputs = {"value": "test input"}
        run_id = "test-run-123"
        
        with patch('services.temporal.activities.node_executor.publish_node_status') as mock_publish:
            result = await execute_input_node_activity(node_id, config, inputs, run_id)
        
        assert result["output"] == "test input"
        assert result["output_type"] == "text"
        assert mock_publish.call_count == 2  # running + success
    
    @pytest.mark.asyncio
    async def test_execute_input_node_with_default_value(self):
        """Test input node uses config value when input not provided"""
        node_id = "node-1"
        config = {"value": "default value"}
        inputs = {}
        run_id = "test-run-123"
        
        with patch('services.temporal.activities.node_executor.publish_node_status'):
            result = await execute_input_node_activity(node_id, config, inputs, run_id)
        
        assert result["output"] == "default value"
    
    @pytest.mark.asyncio
    async def test_execute_python_node_mocked(self):
        """Test Python node execution with mocked Docker"""
        node_id = "node-1"
        config = {"code": "def main(inputs): return {'result': inputs['value']}", "requirements": ""}
        inputs = {"value": "test"}
        run_id = "test-run-123"
        
        mock_result = {
            "output": {"result": "test"},
            "output_type": "text",
            "error": None
        }
        
        with patch('services.docker.executor.DockerExecutor') as mock_docker_class:
            mock_executor = MagicMock()
            mock_executor.execute_python_node = AsyncMock(return_value=mock_result)
            mock_docker_class.return_value = mock_executor
            
            with patch('services.temporal.activities.node_executor.publish_node_status'):
                result = await execute_python_node_activity(node_id, config, inputs, run_id)
        
        assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_execute_llm_node_mocked(self):
        """Test LLM node execution with mocked LLM executor"""
        node_id = "node-1"
        config = {"prompt": "Say hello", "configId": None}
        inputs = {}
        run_id = "test-run-123"
        
        mock_result = {
            "output": "Hello!",
            "output_type": "text",
            "tokens_used": 10
        }
        
        with patch('services.llm.executor.LLMExecutor') as mock_llm_class:
            mock_executor = MagicMock()
            mock_executor.execute_llm_node = AsyncMock(return_value=mock_result)
            mock_llm_class.return_value = mock_executor
            
            with patch('services.temporal.activities.node_executor.publish_node_status'):
                result = await execute_llm_node_activity(node_id, config, inputs, run_id)
        
        assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_execute_memory_node(self):
        """Test memory node execution"""
        node_id = "node-1"
        config = {}
        inputs = {}
        run_id = "test-run-123"
        
        with patch('services.temporal.activities.node_executor.publish_node_status'):
            result = await execute_memory_node_activity(node_id, config, inputs, run_id)
        
        assert "output" in result
        assert "output_type" in result
    
    @pytest.mark.asyncio
    async def test_node_activity_error_handling(self):
        """Test that node activities publish error status on failure"""
        node_id = "node-1"
        config = {}
        inputs = {}
        run_id = "test-run-123"
        
        with patch('services.temporal.activities.node_executor.publish_node_status') as mock_publish:
            with patch('services.docker.executor.DockerExecutor') as mock_docker:
                mock_executor = MagicMock()
                mock_executor.execute_python_node = AsyncMock(side_effect=Exception("Test error"))
                mock_docker.return_value = mock_executor
                
                with pytest.raises(Exception):
                    await execute_python_node_activity(node_id, config, inputs, run_id)
        
        # Should publish error status
        assert mock_publish.call_count >= 1
        # Check last call was error status
        error_call = mock_publish.call_args_list[-1]
        assert error_call[0][2] == "error"  # status parameter


@pytest.mark.unit
class TestWorkflowActivities:
    """Test workflow-level activities"""
    
    @pytest.mark.asyncio
    async def test_save_run_results_activity(self, test_db):
        """Test saving run results to database"""
        from database.models import RunHistory, Workflow
        from uuid import uuid4
        from unittest.mock import MagicMock, patch
        
        # Create workflow first
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        run_id = str(uuid4())
        
        # Create run record with snapshot
        run = RunHistory(
            id=run_id,
            workflow_id=workflow.id,
            status="running",
            snapshot={}
        )
        test_db.add(run)
        test_db.commit()
        
        final_state = {
            "inputs": {},
            "node_outputs": {
                "node-1": {"output": "test", "status": "success"}
            },
            "run_id": run_id
        }
        
        # Mock SessionLocal to return test_db session
        # Create a mock sessionmaker that returns test_db
        mock_sessionmaker = MagicMock(return_value=test_db)
        
        with patch('database.connection.SessionLocal', mock_sessionmaker):
            await save_run_results_activity(run_id, final_state, "success")
        
        # Query fresh from database to avoid session issues
        updated_run = test_db.query(RunHistory).filter(RunHistory.id == run_id).first()
        
        assert updated_run.status == "success"
        assert updated_run.snapshot == final_state
        assert updated_run.total_nodes == 1
        assert updated_run.completed_nodes == 1
    
    @pytest.mark.asyncio
    async def test_publish_workflow_status_activity(self):
        """Test publishing workflow status"""
        run_id = "test-run-123"
        status = "started"
        data = {}
        
        with patch('services.temporal.activities.node_executor.publish_node_status') as mock_publish:
            await publish_workflow_status_activity(run_id, status, data)
        
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0]
        assert call_args[0] == run_id
        assert call_args[1] == "__workflow__"
        assert call_args[2] == status

