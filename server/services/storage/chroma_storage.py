# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
ChromaDB self-hosted vector storage backend.
"""
from typing import Dict, Any, List, Optional, Union
import chromadb
from chromadb.config import Settings
import json

from services.storage.base import StorageBackend


class ChromaStorage(StorageBackend):
    """ChromaDB self-hosted vector storage"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.persist_directory = config.get("persist_directory", "/app/storage/chroma")
        self.collection_name = config.get("collection_name", "memory")
        self.embedding_function = config.get("embedding_function", "sentence-transformers")
        self.client = None
        self.collection = None
    
    def initialize(self) -> None:
        """Initialize Chroma client and collection"""
        if self._initialized:
            return
        
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}  # Cosine similarity
        )
        
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """Store value in Chroma (requires embedding)"""
        if not self._initialized:
            self.initialize()
        
        if embedding is None:
            raise ValueError("Chroma storage requires embedding for vector search")
        
        # Convert value to string for storage
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        # Prepare metadata
        doc_metadata = metadata or {}
        doc_metadata["_value"] = value_str
        
        # Store in Chroma
        self.collection.upsert(
            ids=[key],
            embeddings=[embedding],
            documents=[value_str],
            metadatas=[doc_metadata]
        )
        
        return key
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from Chroma by key"""
        if not self._initialized:
            self.initialize()
        
        try:
            result = self.collection.get(ids=[key])
            if result["ids"]:
                value_str = result["documents"][0]
                # Try to parse as JSON, otherwise return as string
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    return value_str
            return None
        except Exception:
            return None
    
    def search(
        self,
        query: Union[str, List[float]],
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search in Chroma (vector similarity search).

        Expects a vector. Auto-embedding for text queries is handled by
        ``StorageClient`` (issue14) before this method is called — by the
        time we get here, ``query`` should be a list of floats.
        """
        if not self._initialized:
            self.initialize()

        if isinstance(query, str):
            raise ValueError(
                "Chroma vector search requires an embedding vector. "
                "If you want auto-embedding from text, set "
                "config.embedding_function on the storage."
            )

        # Vector similarity search
        results = self.collection.query(
            query_embeddings=[query],
            n_results=limit,
            where=metadata_filter  # Optional metadata filtering
        )
        
        return [
            {
                "key": results["ids"][0][i],
                "value": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": 1.0 - results["distances"][0][i]  # Convert distance to similarity
            }
            for i in range(len(results["ids"][0]))
        ]
    
    def delete(self, key: str) -> bool:
        """Delete value from Chroma"""
        if not self._initialized:
            self.initialize()
        
        try:
            self.collection.delete(ids=[key])
            return True
        except Exception:
            return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (optionally filtered by prefix)"""
        if not self._initialized:
            self.initialize()
        
        # Chroma doesn't support prefix filtering directly
        # Get all and filter in Python
        all_data = self.collection.get()
        keys = all_data["ids"]
        
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        
        return keys
    
    def close(self) -> None:
        """Close Chroma connection (no-op for persistent client)"""
        pass

