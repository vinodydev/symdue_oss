"""
MongoDB document storage backend.
"""
from typing import Dict, Any, List, Optional, Union
from pymongo import MongoClient
from pymongo.collection import Collection
import json

from services.storage.base import StorageBackend


class MongoDBStorage(StorageBackend):
    """MongoDB document storage"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get("connection_string")
        self.database_name = config.get("database", "graphmind")
        self.collection_name = config.get("collection", "memory")
        self.client = None
        self.collection = None
    
    def initialize(self) -> None:
        """Initialize MongoDB connection"""
        if self._initialized:
            return
        
        if not self.connection_string:
            raise ValueError("MongoDB connection_string is required")
        
        self.client = MongoClient(self.connection_string)
        db = self.client[self.database_name]
        self.collection = db[self.collection_name]
        
        # Create index on key for fast lookups
        self.collection.create_index("key", unique=True)
        
        # Create text index for search
        try:
            self.collection.create_index([("value", "text")])
        except Exception:
            # Index might already exist, ignore
            pass
        
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store value in MongoDB"""
        if not self._initialized:
            self.initialize()
        
        document = {
            "key": key,
            "value": value,
            "metadata": metadata or {}
        }
        
        self.collection.update_one(
            {"key": key},
            {"$set": document},
            upsert=True
        )
        
        return key
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from MongoDB"""
        if not self._initialized:
            self.initialize()
        
        document = self.collection.find_one({"key": key})
        if document:
            return document.get("value")
        return None
    
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search in MongoDB (text search)"""
        if not self._initialized:
            self.initialize()
        
        # Build query
        search_query = {"$text": {"$search": str(query)}}
        
        if metadata_filter:
            search_query.update(metadata_filter)
        
        # Execute search
        cursor = self.collection.find(
            search_query,
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        results = []
        for doc in cursor:
            results.append({
                "key": doc["key"],
                "value": doc["value"],
                "metadata": doc.get("metadata", {}),
                "score": doc.get("score", 1.0)
            })
        
        return results
    
    def delete(self, key: str) -> bool:
        """Delete value from MongoDB"""
        if not self._initialized:
            self.initialize()
        
        result = self.collection.delete_one({"key": key})
        return result.deleted_count > 0
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (optionally filtered by prefix)"""
        if not self._initialized:
            self.initialize()
        
        query = {}
        if prefix:
            query = {"key": {"$regex": f"^{prefix}"}}
        
        cursor = self.collection.find(query, {"key": 1})
        return [doc["key"] for doc in cursor]
    
    def close(self) -> None:
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
        self._initialized = False

