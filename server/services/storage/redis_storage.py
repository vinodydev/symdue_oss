"""
Redis in-memory storage backend.
"""
from typing import Dict, Any, List, Optional, Union
import redis
import json

from services.storage.base import StorageBackend


class RedisStorage(StorageBackend):
    """Redis in-memory storage"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get("connection_string", "redis://localhost:6379/0")
        self.key_prefix = config.get("key_prefix", "memory:")
        self.default_ttl = config.get("default_ttl")  # Optional TTL in seconds
        self.client = None
    
    def initialize(self) -> None:
        """Initialize Redis connection"""
        if self._initialized:
            return
        
        self.client = redis.from_url(
            self.connection_string,
            decode_responses=False  # We'll handle encoding ourselves
        )
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store value in Redis"""
        if not self._initialized:
            self.initialize()
        
        full_key = f"{self.key_prefix}{key}"
        
        # Serialize value
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value).encode('utf-8')
        else:
            serialized = json.dumps({"_value": str(value)}).encode('utf-8')
        
        # Store with optional TTL
        if self.default_ttl:
            self.client.setex(full_key, self.default_ttl, serialized)
        else:
            self.client.set(full_key, serialized)
        
        # Store metadata separately if provided
        if metadata:
            meta_key = f"{full_key}:meta"
            self.client.set(meta_key, json.dumps(metadata).encode('utf-8'))
        
        return key
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from Redis (synchronous)"""
        if not self._initialized:
            self.initialize()
        
        full_key = f"{self.key_prefix}{key}"
        data = self.client.get(full_key)
        
        if data is None:
            return None
        
        # Deserialize
        value = json.loads(data.decode('utf-8'))
        # Unwrap if stored as {"_value": "..."}
        if isinstance(value, dict) and "_value" in value and len(value) == 1:
            return value["_value"]
        return value
    
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search in Redis (simple pattern matching, synchronous)"""
        if not self._initialized:
            self.initialize()
        
        # Redis doesn't have built-in search, so we scan keys
        # For production, consider using RediSearch module
        pattern = f"{self.key_prefix}*"
        results = []
        
        for key in self.client.scan_iter(match=pattern):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if key_str.endswith(":meta"):
                continue
            
            # Extract the original key (remove prefix)
            original_key = key_str.replace(self.key_prefix, "")
            value = self.retrieve(original_key)
            if value:
                # Simple text matching
                query_str = str(query)
                value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                
                if query_str.lower() in value_str.lower():
                    results.append({
                        "key": original_key,
                        "value": value,
                        "metadata": {},
                        "score": 1.0
                    })
                    
                    if len(results) >= limit:
                        break
        
        return results
    
    def delete(self, key: str) -> bool:
        """Delete value from Redis"""
        if not self._initialized:
            self.initialize()
        
        full_key = f"{self.key_prefix}{key}"
        result = self.client.delete(full_key, f"{full_key}:meta")
        return result > 0
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (optionally filtered by prefix)"""
        if not self._initialized:
            self.initialize()
        
        pattern = f"{self.key_prefix}{prefix or ''}*"
        keys = []
        
        for key in self.client.scan_iter(match=pattern):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if not key_str.endswith(":meta"):
                # Remove prefix to get original key
                original_key = key_str.replace(self.key_prefix, "")
                keys.append(original_key)
        
        return keys
    
    def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            self.client.close()
        self._initialized = False

