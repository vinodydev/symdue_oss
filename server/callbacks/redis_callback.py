# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Redis callback handler for LangGraph execution
Captures node outputs and publishes status updates via Redis Pub/Sub
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
import redis.asyncio as redis
from config.settings import get_settings


class RedisStreamCallback:
    """
    LangGraph callback that publishes node execution events to Redis.
    
    This enables real-time UI updates via WebSocket connections.
    """
    
    def __init__(self, run_id: str):
        """
        Initialize callback with run ID.
        
        Args:
            run_id: Run history ID for tracking
        """
        self.run_id = run_id
        self.snapshot: Dict[str, Dict[str, Any]] = {}
        self.node_outputs: Dict[str, Any] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.settings = get_settings()
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.settings.redis_url,
                decode_responses=False  # We'll encode JSON ourselves
            )
        return self.redis_client
    
    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Called when a node starts executing"""
        # Extract node ID from serialized data or run_id
        node_id = self._extract_node_id(serialized, run_id)
        if not node_id:
            return
        
        # Initialize snapshot entry
        self.snapshot[node_id] = {
            "node_id": node_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "input": inputs
        }
        
        # Publish node start event
        await self._publish_node_status(
            node_id,
            "running",
            {"input": inputs}
        )
    
    async def on_chain_end(
        self,
        serialized: Dict[str, Any],
        outputs: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Called when a node completes successfully"""
        node_id = self._extract_node_id(serialized, run_id)
        if not node_id:
            return
        
        # Calculate duration
        started_at = datetime.fromisoformat(self.snapshot[node_id]["started_at"])
        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()
        
        # Update snapshot
        self.snapshot[node_id].update({
            "status": "success",
            "output": outputs,
            "completed_at": completed_at.isoformat(),
            "duration": duration
        })
        
        # Store output for state
        self.node_outputs[node_id] = outputs
        
        # Publish node complete event
        await self._publish_node_status(
            node_id,
            "success",
            {"output": outputs, "duration": duration}
        )
    
    async def on_chain_error(
        self,
        serialized: Dict[str, Any],
        error: Exception,
        *,
        run_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Called when a node execution fails"""
        node_id = self._extract_node_id(serialized, run_id)
        if not node_id:
            return
        
        # Calculate duration if started
        duration = None
        if node_id in self.snapshot and "started_at" in self.snapshot[node_id]:
            started_at = datetime.fromisoformat(self.snapshot[node_id]["started_at"])
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()
        
        # Update snapshot
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": self._format_traceback(error)
        }
        
        self.snapshot[node_id].update({
            "status": "error",
            "error": error_info,
            "completed_at": datetime.utcnow().isoformat(),
            "duration": duration
        })
        
        # Publish node error event
        await self._publish_node_status(
            node_id,
            "error",
            {"error": error_info}
        )
    
    def _extract_node_id(
        self,
        serialized: Dict[str, Any],
        run_id: Optional[str]
    ) -> Optional[str]:
        """
        Extract node ID from LangGraph callback data.
        
        LangGraph callbacks provide node information in serialized data.
        We need to extract the node ID to track which node is executing.
        """
        # Try to get node ID from serialized data
        if "id" in serialized:
            return serialized["id"]
        
        # Try to get from name (LangGraph uses node names)
        if "name" in serialized:
            return serialized["name"]
        
        # Fallback: use run_id if it looks like a node ID
        if run_id and len(run_id) > 10:
            return run_id
        
        return None
    
    def _format_traceback(self, error: Exception) -> str:
        """Format exception traceback as string"""
        import traceback
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))
    
    async def _publish_node_status(
        self,
        node_id: str,
        status: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Publish node status update to Redis Pub/Sub.
        
        Args:
            node_id: Node ID
            status: Status ("running", "success", "error")
            data: Additional data (output, error, etc.)
        """
        try:
            redis_client = await self._get_redis_client()
            message = {
                "type": "NODE_STATUS",
                "run_id": self.run_id,
                "node_id": node_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }
            
            # Publish to run_updates channel
            await redis_client.publish(
                f"run_updates:{self.run_id}",
                json.dumps(message)
            )
        except Exception as e:
            # Log error but don't fail execution
            print(f"Failed to publish node status: {e}")
    
    def get_node_outputs(self) -> Dict[str, Any]:
        """Get captured node outputs"""
        return self.node_outputs.copy()
    
    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get complete execution snapshot"""
        return self.snapshot.copy()
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None

