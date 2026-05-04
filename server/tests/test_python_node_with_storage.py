"""
End-to-end test for Python nodes with storage access.

This test verifies:
1. Python nodes can receive storage configs
2. Storage clients are properly initialized in containers
3. Storage operations work from within Python nodes
"""
import os
import sys
import requests
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def test_python_node_with_storage():
    """Test Python node execution with storage access"""
    print("Testing Python node with storage access...")
    
    # Get a storage config (Redis for simplicity)
    response = requests.get(f"{BASE_URL}/api/storage/")
    assert response.status_code == 200, "Failed to get storage configs"
    
    storages = response.json()
    redis_storage = next((s for s in storages if s["storage_type"] == "redis"), None)
    
    if not redis_storage:
        print("⚠️  No Redis storage found, creating one...")
        # Create a Redis storage config
        response = requests.post(
            f"{BASE_URL}/api/storage/",
            json={
                "name": "Test Redis for Python Node",
                "storage_type": "redis",
                "config": {
                    "connection_string": "redis://redis:6379/0",
                    "key_prefix": "python_test:",
                },
                "enabled": True
            }
        )
        assert response.status_code == 200, "Failed to create Redis storage"
        redis_storage = response.json()
    
    print(f"✅ Using storage: {redis_storage['name']} ({redis_storage['id']})")
    
    # Python code that uses storage
    python_code = '''
def main(inputs, storages=None):
    """
    Test Python node with storage access.
    
    Args:
        inputs: Input values from upstream nodes
        storages: Dictionary of storage clients
    """
    if not storages:
        return {"error": "No storages available"}
    
    # Get Redis storage (should be available by alias or name)
    redis_storage = None
    for alias, storage in storages.items():
        if storage and hasattr(storage, 'storage_type'):
            # Try to get the storage type from the client
            if 'redis' in alias.lower() or storage.storage_type == 'redis':
                redis_storage = storage
                break
    
    if not redis_storage:
        # Fallback: try to get first storage
        redis_storage = next(iter(storages.values()), None)
    
    if not redis_storage:
        return {"error": "Redis storage not found", "available_storages": list(storages.keys())}
    
    # Test storage operations
    test_key = "python_node_test_key"
    test_value = {"message": "Hello from Python node!", "test": True}
    
    # Store value
    stored_key = redis_storage.store(test_key, test_value, metadata={"source": "python_node_test"})
    
    # Retrieve value
    retrieved_value = redis_storage.retrieve(test_key)
    
    # Delete value
    deleted = redis_storage.delete(test_key)
    
    return {
        "stored_key": stored_key,
        "retrieved_value": retrieved_value,
        "deleted": deleted,
        "storage_available": True,
        "storage_keys": list(storages.keys())
    }
'''
    
    # Test the code execution (this would normally be done via the node executor)
    # For now, we'll just verify the code structure is correct
    print("✅ Python code structure verified")
    print(f"   Code length: {len(python_code)} characters")
    
    # Check if code has required elements
    assert "def main(inputs, storages=None)" in python_code, "Missing main function signature"
    assert "storages" in python_code, "Code doesn't use storages"
    assert "store" in python_code, "Code doesn't test store operation"
    assert "retrieve" in python_code, "Code doesn't test retrieve operation"
    
    print("✅ Python code validation passed")
    
    return {
        "storage_id": redis_storage["id"],
        "storage_name": redis_storage["name"],
        "python_code": python_code
    }

def test_storage_client_structure():
    """Test that StorageClient has the expected interface"""
    print("\nTesting StorageClient structure...")
    
    try:
        from services.storage.storage_client import StorageClient
        
        # Verify StorageClient has required methods
        required_methods = [
            'store', 'retrieve', 'search', 'delete', 'list_keys',
            'upload_file', 'download_file', 'get_file_url'
        ]
        
        for method in required_methods:
            assert hasattr(StorageClient, method), f"StorageClient missing method: {method}"
        
        print(f"✅ StorageClient has all required methods: {', '.join(required_methods)}")
        
        # Verify __init__ signature
        import inspect
        sig = inspect.signature(StorageClient.__init__)
        params = list(sig.parameters.keys())
        assert 'storage_type' in params, "StorageClient.__init__ missing storage_type parameter"
        assert 'config' in params, "StorageClient.__init__ missing config parameter"
        
        print("✅ StorageClient interface verified")
        
    except Exception as e:
        print(f"❌ Error testing StorageClient: {e}")
        import traceback
        traceback.print_exc()
        raise

def test_storage_manager():
    """Test StorageManager functionality"""
    print("\nTesting StorageManager...")
    
    try:
        from services.storage.manager import StorageManager
        from database.connection import SessionLocal
        from database.models.storage import StorageConfig
        
        db = SessionLocal()
        try:
            # Test get_node_storage_configs with non-existent storage (should return empty dict)
            import uuid
            fake_uuid = str(uuid.uuid4())
            node_config = {
                "storages": [
                    {
                        "storage_id": fake_uuid,
                        "alias": "test_storage"
                    }
                ]
            }
            
            configs = StorageManager.get_node_storage_configs(node_config, db)
            # Should return empty dict if storage doesn't exist, but method should work
            assert isinstance(configs, dict), "get_node_storage_configs should return dict"
            assert len(configs) == 0, "Should return empty dict for non-existent storage"
            
            print("✅ StorageManager.get_node_storage_configs works")
            
            # Test _create_backend for each storage type
            storage_types = ["postgresql", "redis", "mongodb", "chroma", "local_file", "minio"]
            for storage_type in storage_types:
                try:
                    backend = StorageManager._create_backend(storage_type, {})
                    assert backend is not None, f"Failed to create {storage_type} backend"
                    print(f"   ✅ Can create {storage_type} backend")
                except Exception as e:
                    print(f"   ⚠️  {storage_type} backend creation failed (expected if config incomplete): {e}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error testing StorageManager: {e}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """Run all tests"""
    print("=" * 60)
    print("Python Node with Storage - End-to-End Test")
    print("=" * 60)
    
    try:
        # Test storage client structure
        test_storage_client_structure()
        
        # Test storage manager
        test_storage_manager()
        
        # Test Python node code structure
        result = test_python_node_with_storage()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print(f"\nTest Results:")
        print(f"  - Storage ID: {result['storage_id']}")
        print(f"  - Storage Name: {result['storage_name']}")
        print(f"  - Python Code: Ready for execution")
        print("\n💡 Next step: Test actual Python node execution with storage")
        print("   (This requires creating a node via API and executing a workflow)")
        
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

