# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for storage helpers - converting storage configs to environment variables
"""
import pytest
from database.connection import SessionLocal
from database.models import StorageConfig
from utils.storage_helpers import storage_config_to_env_vars
import uuid


@pytest.fixture
def db():
    """Database session fixture"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestStorageHelpers:
    """Test storage config to env var conversion"""
    
    def test_postgresql_storage_to_env_vars(self):
        """Test PostgreSQL storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test PostgreSQL",
            storage_type="postgresql",
            config={
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "user": "testuser",
                "password": "testpass",
                "connection_string": "postgresql://testuser:testpass@localhost:5432/testdb"
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert "DATABASE_URL" in env_vars
        assert env_vars["POSTGRES_HOST"] == "localhost"
        assert env_vars["POSTGRES_PORT"] == "5432"
        assert env_vars["POSTGRES_DB"] == "testdb"
        assert env_vars["POSTGRES_USER"] == "testuser"
        assert env_vars["POSTGRES_PASSWORD"] == "testpass"
        assert env_vars["STORAGE_NAME"] == "Test PostgreSQL"
        assert env_vars["STORAGE_TYPE"] == "postgresql"
    
    def test_redis_storage_to_env_vars(self):
        """Test Redis storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test Redis",
            storage_type="redis",
            config={
                "host": "redis-host",
                "port": 6379,
                "password": "redispass",
                "db": 1,
                "connection_string": "redis://:redispass@redis-host:6379/1"
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert "REDIS_URL" in env_vars
        assert env_vars["REDIS_HOST"] == "redis-host"
        assert env_vars["REDIS_PORT"] == "6379"
        assert env_vars["REDIS_PASSWORD"] == "redispass"
        assert env_vars["REDIS_DB"] == "1"
        assert env_vars["STORAGE_NAME"] == "Test Redis"
    
    def test_minio_storage_to_env_vars(self):
        """Test MinIO storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test MinIO",
            storage_type="minio",
            config={
                "endpoint": "http://minio:9000",
                "access_key": "minioadmin",
                "secret_key": "minioadmin",
                "bucket_name": "test-bucket",
                "region": "us-east-1",
                "use_ssl": False,
                "path_style": True
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert env_vars["S3_ENDPOINT"] == "http://minio:9000"
        assert env_vars["S3_ACCESS_KEY"] == "minioadmin"
        assert env_vars["S3_SECRET_KEY"] == "minioadmin"
        assert env_vars["S3_BUCKET"] == "test-bucket"
        assert env_vars["S3_REGION"] == "us-east-1"
        assert env_vars["S3_USE_SSL"] == "false"
        assert env_vars["S3_PATH_STYLE"] == "true"
        assert env_vars["STORAGE_NAME"] == "Test MinIO"
    
    def test_s3_storage_to_env_vars(self):
        """Test S3 storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test S3",
            storage_type="s3",
            config={
                "endpoint": "https://s3.amazonaws.com",
                "access_key": "AKIAIOSFODNN7EXAMPLE",
                "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "bucket_name": "my-bucket",
                "region": "us-west-2"
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert env_vars["S3_ENDPOINT"] == "https://s3.amazonaws.com"
        assert env_vars["S3_ACCESS_KEY"] == "AKIAIOSFODNN7EXAMPLE"
        assert env_vars["S3_BUCKET"] == "my-bucket"
        assert env_vars["S3_REGION"] == "us-west-2"
    
    def test_mongodb_storage_to_env_vars(self):
        """Test MongoDB storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test MongoDB",
            storage_type="mongodb",
            config={
                "host": "mongodb-host",
                "port": 27017,
                "database": "testdb",
                "user": "mongouser",
                "password": "mongopass",
                "connection_string": "mongodb://mongouser:mongopass@mongodb-host:27017/testdb"
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert "MONGODB_URL" in env_vars
        assert env_vars["MONGODB_HOST"] == "mongodb-host"
        assert env_vars["MONGODB_PORT"] == "27017"
        assert env_vars["MONGODB_DB"] == "testdb"
        assert env_vars["MONGODB_USER"] == "mongouser"
        assert env_vars["MONGODB_PASSWORD"] == "mongopass"
    
    def test_chroma_storage_to_env_vars(self):
        """Test ChromaDB storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test Chroma",
            storage_type="chroma",
            config={
                "persist_directory": "/data/chroma",
                "host": "chroma-host",
                "port": 8000
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert env_vars["CHROMA_PERSIST_DIRECTORY"] == "/data/chroma"
        assert env_vars["CHROMA_HOST"] == "chroma-host"
        assert env_vars["CHROMA_PORT"] == "8000"
    
    def test_local_file_storage_to_env_vars(self):
        """Test local file storage conversion"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Test Local",
            storage_type="local_file",
            config={
                "root_path": "/data/files"
            }
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert env_vars["LOCAL_STORAGE_ROOT"] == "/data/files"
        assert env_vars["STORAGE_NAME"] == "Test Local"
    
    def test_storage_always_includes_name_and_type(self):
        """Test that storage name and type are always included"""
        storage = StorageConfig(
            id=uuid.uuid4(),
            name="Any Storage",
            storage_type="postgresql",
            config={}
        )
        
        env_vars = storage_config_to_env_vars(storage)
        
        assert "STORAGE_NAME" in env_vars
        assert "STORAGE_TYPE" in env_vars
        assert env_vars["STORAGE_NAME"] == "Any Storage"
        assert env_vars["STORAGE_TYPE"] == "postgresql"

