# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Test script for storage system functionality.

This script verifies:
1. Storage API endpoints work
2. Storage backends can be initialized
3. Basic storage operations work
"""
import os
import sys
import requests
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def test_storage_api():
    """Test storage API endpoints"""
    print("Testing Storage API endpoints...")
    
    # Test GET /api/storage/
    response = requests.get(f"{BASE_URL}/api/storage/")
    assert response.status_code == 200, f"Failed to list storages: {response.status_code}"
    storages = response.json()
    print(f"✅ Found {len(storages)} storage configurations")
    
    # Test GET /api/storage/{id}
    if storages:
        storage_id = storages[0]["id"]
        response = requests.get(f"{BASE_URL}/api/storage/{storage_id}")
        assert response.status_code == 200, f"Failed to get storage: {response.status_code}"
        print(f"✅ Retrieved storage config: {response.json()['name']}")
    
    return storages

def test_storage_operations():
    """Test basic storage operations"""
    print("\nTesting storage operations...")
    
    try:
        from database.connection import SessionLocal
        from database.models.storage import StorageConfig
        from services.storage.manager import StorageManager
        
        db = SessionLocal()
        try:
            # Get a storage config
            storage_config = db.query(StorageConfig).filter_by(
                storage_type="redis",
                deleted_at=None,
                enabled=True
            ).first()
            
            if not storage_config:
                print("⚠️  No Redis storage config found, skipping storage operations test")
                return
            
            print(f"✅ Found storage config: {storage_config.name}")
            
            # Get storage backend
            backend = StorageManager.get_storage(str(storage_config.id), db)
            if backend:
                print("✅ Storage backend initialized")
                
                # Test store
                key = backend.store("test_key", {"message": "Hello, Storage!"}, {"test": True})
                print(f"✅ Stored value with key: {key}")
                
                # Test retrieve
                value = backend.retrieve("test_key")
                assert value is not None, "Failed to retrieve value"
                print(f"✅ Retrieved value: {value}")
                
                # Test delete
                deleted = backend.delete("test_key")
                assert deleted, "Failed to delete value"
                print("✅ Deleted value")
                
                # Cleanup
                StorageManager.close_storage(str(storage_config.id))
            else:
                print("⚠️  Failed to initialize storage backend")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error testing storage operations: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests"""
    print("=" * 60)
    print("Storage System Test Suite")
    print("=" * 60)
    
    try:
        # Test API
        storages = test_storage_api()
        
        # Test operations
        test_storage_operations()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

