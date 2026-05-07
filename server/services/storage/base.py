# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Base storage backend interface.

All methods are synchronous (no async/await). By the time
the program ends, everything should be deterministic (all writes completed).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union


class StorageBackend(ABC):
    """
    Abstract base class for all storage backends.
    
    **IMPORTANT**: All methods are synchronous (no async/await). By the time
    the program ends, everything should be deterministic (all writes completed).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage backend.
        
        Args:
            config: Storage-specific configuration dictionary
        """
        self.config = config
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize connection and create necessary structures (synchronous)"""
        pass
    
    @abstractmethod
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a value (synchronous).
        
        Args:
            key: Storage key/identifier
            value: Value to store (dict, list, string, etc.)
            metadata: Optional metadata (tags, timestamps, etc.)
        
        Returns:
            Storage key/ID
        """
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by key (synchronous).
        
        Args:
            key: Storage key/identifier
        
        Returns:
            Stored value or None if not found
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for values (synchronous).
        
        Args:
            query: Text query (for full-text search) or embedding vector (for vector search)
            limit: Maximum number of results
            metadata_filter: Optional metadata filters
        
        Returns:
            List of results with keys and values: [{"key": "...", "value": ..., "score": ...}, ...]
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a value by key (synchronous).
        
        Args:
            key: Storage key/identifier
        
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """
        List all keys (optionally filtered by prefix) (synchronous).
        
        Args:
            prefix: Optional key prefix filter
        
        Returns:
            List of keys
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close connections and cleanup (synchronous)"""
        pass
    
    # File storage methods (for file storage backends)
    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload a file and return storage key.
        
        Args:
            file_data: File bytes
            file_name: Original filename
            content_type: MIME type
            metadata: Optional metadata
        
        Returns:
            Storage key for retrieving the file
        
        Raises:
            NotImplementedError: If storage backend doesn't support file operations
        """
        raise NotImplementedError("File upload not supported by this storage backend")
    
    def download_file(self, key: str) -> tuple[bytes, str]:
        """
        Download file by key.
        
        Args:
            key: Storage key
        
        Returns:
            tuple: (file_bytes, content_type)
        
        Raises:
            NotImplementedError: If storage backend doesn't support file operations
        """
        raise NotImplementedError("File download not supported by this storage backend")
    
    def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """
        Get file URL (with optional expiration for signed URLs).
        
        Args:
            key: Storage key
            expires_in: Optional expiration in seconds (for signed URLs)
        
        Returns:
            File URL
        
        Raises:
            NotImplementedError: If storage backend doesn't support file operations
        """
        raise NotImplementedError("File URL generation not supported by this storage backend")
    
    def get_connection(self):
        """
        Get a raw database connection for direct SQL/query execution.
        This is optional and only supported by storage backends that have
        a connection concept (e.g., PostgreSQL, MongoDB, Redis).
        
        Returns:
            Raw connection object (type depends on storage backend)
        
        Raises:
            NotImplementedError: If storage backend doesn't support raw connections
        """
        raise NotImplementedError("get_connection not supported by this storage backend")

