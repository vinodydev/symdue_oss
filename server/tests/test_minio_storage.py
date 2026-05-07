# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Test script for MinIO storage functionality.

This script verifies:
1. MinIO service is running
2. Default storage configuration exists
3. Storage operations work correctly
"""
import os
import sys
import requests
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_minio_service():
    """Test if MinIO service is running"""
    print("Testing MinIO service...")
    try:
        response = requests.get("http://localhost:9000/minio/health/live", timeout=5)
        if response.status_code == 200:
            print("✅ MinIO service is running")
            return True
        else:
            print(f"❌ MinIO service returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ MinIO service is not accessible: {e}")
        return False

def test_storage_config_exists():
    """Test if default storage configuration exists in database"""
    print("\nTesting default storage configuration...")
    try:
        from database.connection import SessionLocal
        from database.models.storage import StorageConfig
        
        db = SessionLocal()
        try:
            storage = db.query(StorageConfig).filter_by(
                name="Default File Storage",
                storage_type="minio",
                deleted_at=None
            ).first()
            
            if storage:
                print(f"✅ Default storage config found: {storage.id}")
                print(f"   Name: {storage.name}")
                print(f"   Type: {storage.storage_type}")
                print(f"   Enabled: {storage.enabled}")
                return True, storage
            else:
                print("❌ Default storage config not found")
                return False, None
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error checking storage config: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_storage_operations(storage_config):
    """Test storage operations (upload, download, delete)"""
    print("\nTesting storage operations...")
    try:
        from services.storage.storage_client import StorageClient
        
        # Initialize StorageClient with config
        config = storage_config.config
        client = StorageClient(storage_type="minio", config=config)
        
        # Test file upload
        print("  Testing file upload...")
        test_data = b"Hello, World! This is a test file from MinIO storage test."
        file_key = client.upload_file(
            file_data=test_data,
            file_name="test_file.txt",
            content_type="text/plain",
            metadata={"test": True, "source": "test_script"}
        )
        print(f"  ✅ File uploaded: {file_key}")
        
        # Test file download
        print("  Testing file download...")
        downloaded_data, content_type = client.download_file(file_key)
        if downloaded_data == test_data:
            print(f"  ✅ File downloaded correctly (size: {len(downloaded_data)} bytes)")
        else:
            print(f"  ❌ File content mismatch")
            return False
        
        # Test file URL
        print("  Testing file URL generation...")
        file_url = client.get_file_url(file_key)
        if file_url:
            print(f"  ✅ File URL generated: {file_url}")
        else:
            print(f"  ❌ Failed to generate file URL")
            return False
        
        # Test file deletion
        print("  Testing file deletion...")
        deleted = client.delete(file_key)
        if deleted:
            print(f"  ✅ File deleted successfully")
        else:
            print(f"  ❌ Failed to delete file")
            return False
        
        print("  ✅ All storage operations passed")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing storage operations: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("MinIO Storage Test Suite")
    print("=" * 60)
    
    # Test 1: MinIO service
    if not test_minio_service():
        print("\n❌ MinIO service test failed. Make sure MinIO is running.")
        print("   Start with: docker-compose up -d minio")
        return 1
    
    # Test 2: Storage config
    config_exists, storage_config = test_storage_config_exists()
    if not config_exists:
        print("\n❌ Storage config test failed. Run migrations:")
        print("   cd graph_execution/code/server")
        print("   alembic upgrade head")
        return 1
    
    # Test 3: Storage operations
    if not test_storage_operations(storage_config):
        print("\n❌ Storage operations test failed.")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

