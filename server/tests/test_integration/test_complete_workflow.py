# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Integration test for complete workflow: Create workspace → Add nodes → Create edges → Test
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.mark.integration
def test_complete_workflow(test_db):
    """Test complete workflow from workspace creation to edge creation"""
    # 1. Create workspace
    ws_response = client.post("/api/workspaces", json={"name": "Integration Test"})
    assert ws_response.status_code == 201
    workspace_id = ws_response.json()["id"]
    
    # 2. Create multiple nodes
    node1 = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {"value": "test1"}}
    ).json()
    node2 = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "custom-python", "x": 200, "y": 0, "config_overrides": {}}
    ).json()
    node3 = client.post(
        f"/api/workspaces/{workspace_id}/nodes",
        json={"node_type_id": "custom-llm", "x": 400, "y": 0, "config_overrides": {}}
    ).json()
    
    assert node1["node_type_id"] == "input"
    assert node2["node_type_id"] == "custom-python"
    assert node3["node_type_id"] == "custom-llm"
    
    # 3. Create edges with different weights
    edge1 = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={"source": node1["id"], "target": node2["id"], "weight": 0.9}
    ).json()
    edge2 = client.post(
        f"/api/workspaces/{workspace_id}/edges",
        json={"source": node2["id"], "target": node3["id"], "weight": 0.7}
    ).json()
    
    assert edge1["weight"] == 0.9
    assert edge2["weight"] == 0.7
    
    # 4. Get workspace with all nodes and edges
    workspace = client.get(f"/api/workspaces/{workspace_id}").json()
    assert len(workspace["nodes"]) == 3
    assert len(workspace["edges"]) == 2
    
    # 5. Test a node
    test_result = client.post(
        f"/api/workspaces/{workspace_id}/nodes/{node1['id']}/test",
        json={}
    ).json()
    assert test_result["status"] in ["success", "pending", "error"]
    assert test_result["node_id"] == node1["id"]
    
    # 6. Update edge weight
    updated_edge = client.patch(
        f"/api/workspaces/{workspace_id}/edges/{edge1['id']}",
        json={"weight": 0.95}
    ).json()
    assert updated_edge["weight"] == 0.95
    
    # 7. Update node position
    updated_node = client.patch(
        f"/api/workspaces/{workspace_id}/nodes/{node1['id']}/position",
        json={"x": 50, "y": 50}
    ).json()
    assert updated_node["x"] == 50
    assert updated_node["y"] == 50
    
    # 8. Update workspace transform
    updated_workspace = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"transform": {"x": 100, "y": 200, "k": 1.5}}
    ).json()
    assert updated_workspace["transform"]["x"] == 100
    assert updated_workspace["transform"]["k"] == 1.5
    
    # 9. Delete edge
    delete_response = client.delete(f"/api/workspaces/{workspace_id}/edges/{edge1['id']}")
    assert delete_response.status_code == 204
    
    # 10. Verify edge is deleted
    workspace_after = client.get(f"/api/workspaces/{workspace_id}").json()
    assert len(workspace_after["edges"]) == 1
    
    # 11. Delete node (should also delete connected edges)
    delete_node_response = client.delete(f"/api/workspaces/{workspace_id}/nodes/{node2['id']}")
    assert delete_node_response.status_code == 204
    
    # 12. Verify node is deleted
    workspace_final = client.get(f"/api/workspaces/{workspace_id}").json()
    assert len(workspace_final["nodes"]) == 2  # node1 and node3 remain

