"""
Tests for node API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_node(test_db):
    """Test creating a node"""
    # Create workspace first
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    # Create node
    response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 200, "config_overrides": {}}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["node_type_id"] == "input"
    assert data["x"] == 100
    assert data["y"] == 200
    assert "id" in data


def test_list_nodes(test_db):
    """Test listing nodes in a workspace"""
    # Create workspace and nodes
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "custom-python", "x": 100, "y": 100, "config_overrides": {}}
    )
    
    # List nodes
    response = client.get(f"/api/workspaces/{workspace_id}/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_get_node(test_db):
    """Test getting a node by ID"""
    # Create workspace and node
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 50, "y": 50, "config_overrides": {}}
    )
    node_id = create_response.json()["id"]
    
    # Get the node
    response = client.get(f"/api/workspaces/{workspace_id}/nodes/{node_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == node_id
    assert data["node_type_id"] == "input"


def test_update_node(test_db):
    """Test updating a node"""
    # Create workspace and node
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {"name": "Original"}}
    )
    node_id = create_response.json()["id"]
    
    # Update the node
    response = client.patch(
        f"/api/workspaces/{workspace_id}/nodes/{node_id}",
        json={"config": {"name": "Updated"}}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["config"]["name"] == "Updated"


def test_update_node_position(test_db):
    """Test updating node position"""
    # Create workspace and node
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node_id = create_response.json()["id"]
    
    # Update position
    response = client.patch(
        f"/api/workspaces/{workspace_id}/nodes/{node_id}/position",
        json={"x": 150, "y": 250}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["x"] == 150
    assert data["y"] == 250


def test_delete_node(test_db):
    """Test deleting a node"""
    # Create workspace and node
    ws_response = client.post("/api/workspaces", json={"name": "Node Test"})
    workspace_id = ws_response.json()["id"]
    
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node_id = create_response.json()["id"]
    
    # Delete the node
    response = client.delete(f"/api/workspaces/{workspace_id}/nodes/{node_id}")
    assert response.status_code == 204
    
    # Verify it's deleted (soft delete)
    get_response = client.get(f"/api/workspaces/{workspace_id}/nodes/{node_id}")
    assert get_response.status_code == 404


def test_test_node_endpoint(test_db):
    """Test node test/pre-flight endpoint"""
    # Create workspace and node
    ws_response = client.post("/api/workspaces", json={"name": "Test Node"})
    workspace_id = ws_response.json()["id"]
    
    node_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {"value": "test"}}
    )
    node_id = node_response.json()["id"]
    
    # Test node
    test_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes/{node_id}/test",
        json={}
    )
    assert test_response.status_code == 200
    data = test_response.json()
    assert "status" in data
    assert "node_id" in data
    assert data["node_id"] == node_id
    assert data["node_type_id"] == "input"
    assert "output" in data or "error" in data

