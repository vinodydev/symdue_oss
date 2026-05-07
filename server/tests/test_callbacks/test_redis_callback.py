# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for Redis callback handler
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from callbacks.redis_callback import RedisStreamCallback
from datetime import datetime


@pytest.mark.unit
class TestRedisCallback:
    """Test Redis callback functionality"""
    
    @pytest.mark.asyncio
    async def test_callback_initialization(self):
        """Test callback initialization"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        assert callback.run_id == run_id
        assert callback.snapshot == {}
        assert callback.node_outputs == {}
    
    @pytest.mark.asyncio
    async def test_on_chain_start(self):
        """Test callback on chain start"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        serialized = {"id": "node-1", "name": "node-1"}
        inputs = {"value": "test"}
        
        with patch.object(callback, '_publish_node_status') as mock_publish:
            await callback.on_chain_start(serialized, inputs, run_id="node-1")
        
        assert "node-1" in callback.snapshot
        assert callback.snapshot["node-1"]["status"] == "running"
        mock_publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_chain_end(self):
        """Test callback on chain end"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        # Initialize node in snapshot
        callback.snapshot["node-1"] = {
            "node_id": "node-1",
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }
        
        serialized = {"id": "node-1"}
        outputs = {"output": "result"}
        
        with patch.object(callback, '_publish_node_status') as mock_publish:
            await callback.on_chain_end(serialized, outputs, run_id="node-1")
        
        assert callback.snapshot["node-1"]["status"] == "success"
        assert callback.snapshot["node-1"]["output"] == outputs
        assert "node-1" in callback.node_outputs
        mock_publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_chain_error(self):
        """Test callback on chain error"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        # Initialize node in snapshot
        callback.snapshot["node-1"] = {
            "node_id": "node-1",
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }
        
        serialized = {"id": "node-1"}
        error = ValueError("Test error")
        
        with patch.object(callback, '_publish_node_status') as mock_publish:
            await callback.on_chain_error(serialized, error, run_id="node-1")
        
        assert callback.snapshot["node-1"]["status"] == "error"
        assert "error" in callback.snapshot["node-1"]
        mock_publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_node_outputs(self):
        """Test getting node outputs"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        callback.node_outputs = {
            "node-1": {"output": "result1"},
            "node-2": {"output": "result2"}
        }
        
        outputs = callback.get_node_outputs()
        
        assert outputs == callback.node_outputs
        assert len(outputs) == 2
    
    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        """Test getting snapshot"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        callback.snapshot = {
            "node-1": {"status": "success"},
            "node-2": {"status": "running"}
        }
        
        snapshot = callback.get_snapshot()
        
        assert snapshot == callback.snapshot
        assert len(snapshot) == 2
    
    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing callback"""
        run_id = "test-run-123"
        callback = RedisStreamCallback(run_id)
        
        # Mock redis client
        callback.redis_client = AsyncMock()
        
        await callback.close()
        
        assert callback.redis_client is None

