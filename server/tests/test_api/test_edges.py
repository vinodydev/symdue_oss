# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for edge API endpoints (including Weighted Intelligence)
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_edge_with_weight(test_db):
    """Test creating an edge with weight (Weighted Intelligence)"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    
    response = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={
            "source": node1_id,
            "target": node2_id,
            "weight": 0.75
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["weight"] == 0.75
    assert data["source"] == node1_id
    assert data["target"] == node2_id


def test_create_edge_invalid_weight(test_db):
    """Test creating an edge with invalid weight (> 1.0)"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    
    response = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={
            "source": node1_id,
            "target": node2_id,
            "weight": 1.5  # Invalid: > 1.0
        }
    )
    assert response.status_code == 422  # Validation error


def test_update_edge_weight(test_db):
    """Test updating an edge's weight"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    
    # Create edge
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={
            "source": node1_id,
            "target": node2_id,
            "weight": 0.5
        }
    )
    edge_id = create_response.json()["id"]
    
    # Update weight
    response = client.patch(
        f"/api/workspaces/{workspace_id}/edges/{edge_id}",
        json={"weight": 0.9}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["weight"] == 0.9


def test_list_edges(test_db):
    """Test listing edges in a workspace"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node3_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 200, "y": 200, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    node3_id = node3_response.json()["id"]
    
    # Create edges
    client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={"source": node1_id, "target": node2_id, "weight": 0.5}
    )
    client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={"source": node2_id, "target": node3_id, "weight": 0.8}
    )
    
    # List edges
    response = client.get(f"/api/workspaces/{workspace_id}/edges")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_get_edge(test_db):
    """Test getting an edge by ID"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    
    # Create edge
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={
            "source": node1_id,
            "target": node2_id,
            "weight": 0.75
        }
    )
    edge_id = create_response.json()["id"]
    
    # Get edge
    response = client.get(f"/api/workspaces/{workspace_id}/edges/{edge_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == edge_id
    assert data["source"] == node1_id
    assert data["target"] == node2_id
    assert data["weight"] == 0.75


def test_get_edge_not_found(test_db):
    """Test getting non-existent edge"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    from uuid import uuid4
    fake_edge_id = str(uuid4())
    
    response = client.get(f"/api/workspaces/{workspace_id}/edges/{fake_edge_id}")
    assert response.status_code == 404


def test_delete_edge(test_db):
    """Test deleting an edge (soft delete)"""
    # Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
    workspace_id = ws_response.json()["id"]
    
    # Create nodes
    node1_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
    )
    node2_response = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
    )
    node1_id = node1_response.json()["id"]
    node2_id = node2_response.json()["id"]
    
    # Create edge
    create_response = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={
            "source": node1_id,
            "target": node2_id,
            "weight": 0.5
        }
    )
    edge_id = create_response.json()["id"]
    
    # Delete edge
    response = client.delete(f"/api/workspaces/{workspace_id}/edges/{edge_id}")
    assert response.status_code == 204
    
    # Verify it's deleted (soft delete)
    get_response = client.get(f"/api/workspaces/{workspace_id}/edges/{edge_id}")
    assert get_response.status_code == 404

