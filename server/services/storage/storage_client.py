# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Storage client library for Python nodes.

This module provides a unified interface for accessing storage backends
from within Python node code.

Issue14: when ``config["embedding_function"]`` is set (format
``"<provider>:<model_id>"``), text inputs to ``search()`` / ``store()``
are auto-embedded by calling the backend's ``POST /api/embed`` endpoint.
The model itself runs in the long-lived backend container — never in the
sandbox — so node code is freed from sentence-transformers boilerplate
and per-call model-load cost.
"""
import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, Union


def _backend_url() -> str:
    """URL of the backend service reachable from this container.

    Sandbox containers join the compose network and resolve ``backend`` via
    Docker DNS. Override via ``BACKEND_URL`` env var if needed.
    """
    return os.environ.get("BACKEND_URL", "http://backend:8000").rstrip("/")


def _embed_via_backend(spec: str, texts: List[str], timeout: float = 30.0) -> List[List[float]]:
    """Call the backend's stateless embedding endpoint.

    Body: ``{"spec": "sentence-transformers:...", "texts": [...]}``
    Returns: list of vectors.

    Uses urllib (stdlib) so the sandbox doesn't need ``requests`` installed.
    """
    url = f"{_backend_url()}/api/embed"
    payload = json.dumps({"spec": spec, "texts": texts}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(
            f"Embedding API {e.code} for spec={spec!r}: {body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Embedding API unreachable at {url}: {e.reason}"
        ) from e
    return data["embeddings"]


class StorageClient:
    """
    Storage client that Python nodes can use to access storage backends.
    
    Python nodes run in worker Docker containers. Storage services are accessible
    via connection strings in the storage config (using service names/hosts from
    settings). StorageClient creates StorageBackend instances internally using
    the config, establishing direct connections to storage services.
    
    All operations are synchronous. By the time the program ends, everything
    should be deterministic (all writes completed).
    """
    
    def __init__(self, storage_type: str, config: Dict[str, Any]):
        """
        Initialize storage client with storage type and connection config.
        
        Args:
            storage_type: Storage type (postgresql, redis, mongodb, chroma, local_file, minio, s3)
            config: Storage connection configuration from settings
                - For PostgreSQL: {"connection_string": "postgres://postgres:5432/dbname", "table": "...", ...}
                - For Redis: {"connection_string": "redis://redis:6379/0", "key_prefix": "...", ...}
                - For MongoDB: {"connection_string": "mongodb://mongodb:27017/dbname", "database": "...", ...}
                - For Chroma: {"persist_directory": "...", "collection_name": "...", ...}
                - For MinIO: {"endpoint": "http://minio:9000", "access_key": "...", "secret_key": "...", ...}
        """
        self.storage_type = storage_type
        self.config = config
        self.backend = None
    
    def _get_backend(self):
        """Lazy initialization of storage backend from config (synchronous)"""
        if self.backend is None:
            # Import and create storage backend based on type
            if self.storage_type == "postgresql":
                from services.storage.postgresql_storage import PostgreSQLStorage
                self.backend = PostgreSQLStorage(self.config)
            elif self.storage_type == "redis":
                from services.storage.redis_storage import RedisStorage
                self.backend = RedisStorage(self.config)
            elif self.storage_type == "mongodb":
                from services.storage.mongodb_storage import MongoDBStorage
                self.backend = MongoDBStorage(self.config)
            elif self.storage_type == "chroma":
                from services.storage.chroma_storage import ChromaStorage
                self.backend = ChromaStorage(self.config)
            elif self.storage_type == "local_file":
                from services.storage.local_file_storage import LocalFileStorage
                self.backend = LocalFileStorage(self.config)
            elif self.storage_type == "minio":
                from services.storage.minio_storage import MinIOStorage
                self.backend = MinIOStorage(self.config)
            elif self.storage_type == "s3":
                from services.storage.minio_storage import MinIOStorage
                self.backend = MinIOStorage(self.config)
            else:
                raise ValueError(f"Unknown storage type: {self.storage_type}")
            
            # Initialize the backend (creates connections) - synchronous
            self.backend.initialize()
        
        return self.backend
    
    def _embedding_spec(self) -> Optional[str]:
        """Return ``embedding_function`` from config if set, else None."""
        spec = (self.config or {}).get("embedding_function")
        return spec if isinstance(spec, str) and spec.strip() else None

    def store(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """Store a value. If the storage has ``embedding_function`` configured
        and no explicit ``embedding`` is provided, embed the value's text
        representation via the backend (issue14)."""
        backend = self._get_backend()
        spec = self._embedding_spec()
        if embedding is None and spec is not None:
            text = value if isinstance(value, str) else json.dumps(value)
            embedding = _embed_via_backend(spec, [text])[0]
        # Backends that accept embedding=... (chroma, postgresql) take the
        # vector. Backends that don't will ignore the kwarg.
        try:
            return backend.store(key, value, metadata, embedding)
        except TypeError:
            return backend.store(key, value, metadata)

    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value by key (synchronous)"""
        backend = self._get_backend()
        return backend.retrieve(key)

    def search(
        self,
        query: Union[str, List[float]],
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for values. If ``query`` is a string and the storage has
        ``embedding_function`` configured, auto-embed via backend (issue14).
        If ``query`` is already a vector, pass through unchanged."""
        backend = self._get_backend()
        if isinstance(query, str):
            spec = self._embedding_spec()
            if spec is not None:
                query = _embed_via_backend(spec, [query])[0]
        return backend.search(query, limit, metadata_filter)
    
    def delete(self, key: str) -> bool:
        """Delete a value by key (synchronous)"""
        backend = self._get_backend()
        return backend.delete(key)
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (synchronous)"""
        backend = self._get_backend()
        return backend.list_keys(prefix)
    
    # File storage methods
    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Upload a file (synchronous)"""
        backend = self._get_backend()
        return backend.upload_file(file_data, file_name, content_type, metadata)
    
    def download_file(self, key: str) -> tuple[bytes, str]:
        """Download a file (synchronous)"""
        backend = self._get_backend()
        return backend.download_file(key)
    
    def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL (synchronous)"""
        backend = self._get_backend()
        return backend.get_file_url(key, expires_in)
    
    def get_connection(self):
        """
        Get a raw database connection for direct SQL/query execution.
        Currently only supported for PostgreSQL storage.
        
        Returns:
            Raw connection object (type depends on storage backend)
            For PostgreSQL: psycopg2 connection object
        
        Raises:
            NotImplementedError: If storage backend doesn't support raw connections
        """
        backend = self._get_backend()
        return backend.get_connection()

