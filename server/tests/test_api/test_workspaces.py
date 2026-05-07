# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for workspace API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_workspace(test_db):
    """Test creating a workspace"""
    response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert "id" in data


def test_list_workspaces(test_db):
    """Test listing workspaces"""
    # Create a workspace first
    client.post("/api/workspaces", json={"name": "Test Workspace"})
    
    # List workspaces
    response = client.get("/api/workspaces")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_workspace(test_db):
    """Test getting a workspace by ID"""
    # Create a workspace
    create_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = create_response.json()["id"]
    
    # Get the workspace
    response = client.get(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == workspace_id
    assert data["name"] == "Test Workspace"


def test_update_workspace(test_db):
    """Test updating a workspace"""
    # Create a workspace
    create_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = create_response.json()["id"]
    
    # Update the workspace
    response = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"name": "Updated Workspace"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Workspace"


def test_delete_workspace(test_db):
    """Test deleting a workspace"""
    # Create a workspace
    create_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = create_response.json()["id"]
    
    # Delete the workspace
    response = client.delete(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 204
    
    # Verify it's deleted (soft delete)
    get_response = client.get(f"/api/workspaces/{workspace_id}")
    assert get_response.status_code == 404


def test_restore_workspace(test_db):
    """Test restoring a deleted workspace"""
    # Create a workspace
    create_response = client.post("/api/workspaces", json={"name": "To Restore"})
    workspace_id = create_response.json()["id"]
    
    # Delete the workspace
    client.delete(f"/api/workspaces/{workspace_id}")
    
    # Restore the workspace
    restore_response = client.post(f"/api/workspaces/{workspace_id}/restore")
    assert restore_response.status_code == 200
    data = restore_response.json()
    assert data["id"] == workspace_id
    assert data["name"] == "To Restore"
    
    # Verify it's accessible again
    get_response = client.get(f"/api/workspaces/{workspace_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "To Restore"

