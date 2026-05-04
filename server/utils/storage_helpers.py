"""
Storage configuration helpers for converting storage configs to environment variables.
"""
from typing import Dict, Any
from database.models import StorageConfig


def storage_config_to_env_vars(storage: StorageConfig) -> Dict[str, str]:
    """
    Convert storage configuration to environment variables.
    
    Args:
        storage: StorageConfig instance
        
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    config = storage.config or {}
    
    if storage.storage_type == "postgresql":
        # PostgreSQL storage
        if "connection_string" in config:
            env_vars["DATABASE_URL"] = config.get("connection_string", "")
        env_vars["POSTGRES_HOST"] = str(config.get("host", ""))
        env_vars["POSTGRES_PORT"] = str(config.get("port", 5432))
        env_vars["POSTGRES_DB"] = str(config.get("database", ""))
        env_vars["POSTGRES_USER"] = str(config.get("user", ""))
        env_vars["POSTGRES_PASSWORD"] = str(config.get("password", ""))
        
    elif storage.storage_type == "redis":
        # Redis storage
        if "connection_string" in config:
            env_vars["REDIS_URL"] = config.get("connection_string", "")
        env_vars["REDIS_HOST"] = str(config.get("host", ""))
        env_vars["REDIS_PORT"] = str(config.get("port", 6379))
        if "password" in config:
            env_vars["REDIS_PASSWORD"] = str(config.get("password", ""))
        if "db" in config:
            env_vars["REDIS_DB"] = str(config.get("db", 0))
            
    elif storage.storage_type == "mongodb":
        # MongoDB storage
        if "connection_string" in config:
            env_vars["MONGODB_URL"] = config.get("connection_string", "")
        env_vars["MONGODB_HOST"] = str(config.get("host", ""))
        env_vars["MONGODB_PORT"] = str(config.get("port", 27017))
        env_vars["MONGODB_DB"] = str(config.get("database", ""))
        if "user" in config:
            env_vars["MONGODB_USER"] = str(config.get("user", ""))
        if "password" in config:
            env_vars["MONGODB_PASSWORD"] = str(config.get("password", ""))
            
    elif storage.storage_type == "chroma":
        # ChromaDB storage
        if "persist_directory" in config:
            env_vars["CHROMA_PERSIST_DIRECTORY"] = str(config.get("persist_directory", ""))
        if "host" in config:
            env_vars["CHROMA_HOST"] = str(config.get("host", ""))
        if "port" in config:
            env_vars["CHROMA_PORT"] = str(config.get("port", 8000))
            
    elif storage.storage_type in ("minio", "s3"):
        # MinIO or S3 storage
        env_vars["S3_ENDPOINT"] = str(config.get("endpoint", ""))
        env_vars["S3_ACCESS_KEY"] = str(config.get("access_key", ""))
        env_vars["S3_SECRET_KEY"] = str(config.get("secret_key", ""))
        env_vars["S3_BUCKET"] = str(config.get("bucket_name", ""))
        env_vars["S3_REGION"] = str(config.get("region", "us-east-1"))
        if "use_ssl" in config:
            env_vars["S3_USE_SSL"] = str(config.get("use_ssl", False)).lower()
        if "path_style" in config:
            env_vars["S3_PATH_STYLE"] = str(config.get("path_style", False)).lower()
            
    elif storage.storage_type == "local_file":
        # Local file storage
        if "root_path" in config:
            env_vars["LOCAL_STORAGE_ROOT"] = str(config.get("root_path", ""))
            
    # Add storage name and type for reference
    env_vars["STORAGE_NAME"] = storage.name
    env_vars["STORAGE_TYPE"] = storage.storage_type
    
    return env_vars

