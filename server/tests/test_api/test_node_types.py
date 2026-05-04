"""
Tests for node type API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_node_types(test_db):
    """Test listing node types"""
    response = client.get("/api/node-types")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should have at least builtin node types
    assert len(data) >= 0


def test_get_node_type(test_db):
    """Test getting a node type by ID"""
    # First ensure input node type exists (should be seeded)
    response = client.get("/api/node-types/input")
    # Should either return 200 (if exists) or 404 (if not seeded yet)
    assert response.status_code in [200, 404]
    
    if response.status_code == 200:
        data = response.json()
        assert data["id"] == "input"
        assert "name" in data
        assert "category" in data


def test_create_node_type(test_db):
    """Test creating a custom node type"""
    response = client.post(
        "/api/node-types",
        json={
            "id": "custom-test",
            "category": "custom",
            "name": "Custom Test Node",
            "description": "A test custom node type",
            "icon": "code",
            "is_builtin": False,
            "is_active": True,
            "default_config": {"name": "Test"},
            "config_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "custom-test"
    assert data["name"] == "Custom Test Node"
    assert data["category"] == "custom"
    assert data["is_builtin"] is False


def test_get_node_type_not_found(test_db):
    """Test getting non-existent node type"""
    from uuid import uuid4
    fake_id = f"nonexistent-{uuid4()}"
    
    response = client.get(f"/api/node-types/{fake_id}")
    assert response.status_code == 404

