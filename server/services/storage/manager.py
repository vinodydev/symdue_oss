"""
Storage Manager - Factory and registry for storage backends.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models.storage import StorageConfig
from services.storage.base import StorageBackend
from services.storage.postgresql_storage import PostgreSQLStorage
from services.storage.redis_storage import RedisStorage
from services.storage.mongodb_storage import MongoDBStorage
from services.storage.chroma_storage import ChromaStorage
from services.storage.local_file_storage import LocalFileStorage
from services.storage.minio_storage import MinIOStorage


class StorageManager:
    """Factory and registry for storage backends"""
    
    _backends: Dict[str, StorageBackend] = {}
    
    @classmethod
    def get_storage(
        cls, 
        storage_config_id: str,
        db: Session
    ) -> Optional[StorageBackend]:
        """
        Get or create storage backend instance.
        
        Args:
            storage_config_id: Storage configuration ID
            db: Database session
        
        Returns:
            Storage backend instance or None if not found
        """
        # Check cache
        if storage_config_id in cls._backends:
            return cls._backends[storage_config_id]
        
        # Load from database
        storage_config = db.query(StorageConfig).filter_by(
            id=storage_config_id,
            deleted_at=None,
            enabled=True
        ).first()
        
        if not storage_config:
            return None
        
        # Create backend instance
        backend = cls._create_backend(storage_config.storage_type, storage_config.config)
        backend.initialize()
        
        # Cache it
        cls._backends[storage_config_id] = backend
        
        return backend
    
    @classmethod
    def _create_backend(cls, storage_type: str, config: Dict[str, Any]) -> StorageBackend:
        """Create storage backend instance based on type"""
        if storage_type == "postgresql":
            return PostgreSQLStorage(config)
        elif storage_type == "redis":
            return RedisStorage(config)
        elif storage_type == "mongodb":
            return MongoDBStorage(config)
        elif storage_type == "chroma":
            return ChromaStorage(config)
        elif storage_type == "local_file":
            return LocalFileStorage(config)
        elif storage_type == "minio":
            return MinIOStorage(config)
        elif storage_type == "s3":
            # S3 uses the same implementation as MinIO
            return MinIOStorage(config)
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
    
    @classmethod
    def get_node_storage_configs(
        cls,
        node_config: Dict[str, Any],
        db: Session
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get storage configs for a node from database.
        
        Fetches storage configuration from StorageConfig table (settings) for each
        storage linked to the node. Returns configs (not instances) since Python
        nodes run in separate Docker containers and need to create their own connections.
        
        Args:
            node_config: Node config dict (from node.config JSONB field)
                Contains: {"storages": [{"storage_id": "...", "alias": "..."}, ...]}
            db: Database session
        
        Returns:
            Dict mapping alias to {storage_type, config}
            Example: {
                "main_db": {
                    "storage_type": "postgresql",
                    "config": {"connection_string": "postgres://...", "table": "...", ...}
                },
                "file_storage": {
                    "storage_type": "minio",
                    "config": {"endpoint": "...", "access_key": "...", ...}
                }
            }
        """
        storage_configs = {}
        storage_refs = node_config.get("storages", [])
        
        for storage_ref in storage_refs:
            storage_id = storage_ref.get("storage_id")
            alias = storage_ref.get("alias")
            
            if not storage_id:
                continue
            
            # Validate UUID format before querying
            try:
                import uuid
                uuid.UUID(storage_id)  # Validate UUID format
            except (ValueError, TypeError):
                # Skip invalid UUIDs
                continue
            
            # Query StorageConfig table directly (fetch from settings)
            storage_config = db.query(StorageConfig).filter_by(
                id=storage_id,
                deleted_at=None,
                enabled=True
            ).first()
            
            if storage_config:
                # Generate alias: lowercase, spaces to underscores
                if alias:
                    storage_alias = alias.lower().replace(" ", "_")
                else:
                    # Use storage name (lowercase, spaces to underscores)
                    storage_alias = storage_config.name.lower().replace(" ", "_")
                
                storage_configs[storage_alias] = {
                    "storage_type": storage_config.storage_type,
                    "config": storage_config.config  # Contains connection_string, credentials, etc.
                }
        
        return storage_configs
    
    @classmethod
    def close_storage(cls, storage_config_id: str) -> None:
        """Close and remove storage backend from cache"""
        if storage_config_id in cls._backends:
            cls._backends[storage_config_id].close()
            del cls._backends[storage_config_id]
    
    @classmethod
    def close_all(cls) -> None:
        """Close all cached storage backends"""
        for backend in cls._backends.values():
            backend.close()
        cls._backends.clear()

