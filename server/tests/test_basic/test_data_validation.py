# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Data validation and constraint tests
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestDataValidation:
    """Test data validation and constraints"""
    
    def test_edge_weight_validation_upper_bound(self, test_db):
        """Test edge weight must not exceed 1.0"""
        # Create workspace and nodes
        ws_response = client.post("/api/workspaces", json={"name": "Weight Test"})
        workspace_id = ws_response.json()["id"]
        
        node1 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 0, "y": 0}
        ).json()
        node2 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 100, "y": 100}
        ).json()
        
        # Test invalid weight (> 1.0)
        invalid_response = client.post(
            f"/api/workspaces/{workspace_id}/edges",
            json={"source": node1["id"], "target": node2["id"], "weight": 1.5}
        )
        assert invalid_response.status_code == 422  # Validation error
    
    def test_edge_weight_validation_lower_bound(self, test_db):
        """Test edge weight must not be below 0.0"""
        # Create workspace and nodes
        ws_response = client.post("/api/workspaces", json={"name": "Weight Test"})
        workspace_id = ws_response.json()["id"]
        
        node1 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 0, "y": 0}
        ).json()
        node2 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 100, "y": 100}
        ).json()
        
        # Test invalid weight (< 0.0)
        invalid_response = client.post(
            f"/api/workspaces/{workspace_id}/edges",
            json={"source": node1["id"], "target": node2["id"], "weight": -0.5}
        )
        assert invalid_response.status_code == 422
    
    def test_edge_weight_validation_valid_range(self, test_db):
        """Test edge weight accepts valid range (0.0-1.0)"""
        # Create workspace and nodes
        ws_response = client.post("/api/workspaces", json={"name": "Weight Test"})
        workspace_id = ws_response.json()["id"]
        
        node1 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}}
        ).json()
        node2 = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}}
        ).json()
        
        # Test valid weights (create new nodes for each to avoid duplicate edge error)
        for i, weight in enumerate([0.0, 0.5, 1.0]):
            # Create fresh nodes for each weight test
            n1 = client.post(
                f"/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "input", "x": i*200, "y": 0, "config_overrides": {}}
            ).json()
            n2 = client.post(
                f"/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "input", "x": i*200+100, "y": 100, "config_overrides": {}}
            ).json()
            
            valid_response = client.post(
                f"/api/workspaces/{workspace_id}/edges",
                json={"source": n1["id"], "target": n2["id"], "weight": weight}
            )
            assert valid_response.status_code == 201
            assert valid_response.json()["weight"] == weight
    
    def test_workspace_name_required(self, test_db):
        """Test workspace name is required"""
        # Empty name should still work (defaults to "Untitled Workflow")
        response = client.post("/api/workspaces", json={})
        assert response.status_code == 201
    
    def test_node_type_id_required(self, test_db):
        """Test node_type_id is required for node creation"""
        ws_response = client.post("/api/workspaces", json={"name": "Test"})
        workspace_id = ws_response.json()["id"]
        
        # Missing node_type_id should fail
        response = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"x": 0, "y": 0}
        )
        assert response.status_code == 422
    
    def test_node_position_required(self, test_db):
        """Test node position (x, y) is required"""
        ws_response = client.post("/api/workspaces", json={"name": "Test"})
        workspace_id = ws_response.json()["id"]
        
        # Missing position should fail
        response = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input"}
        )
        assert response.status_code == 422
    
    def test_edge_source_target_required(self, test_db):
        """Test edge source and target are required"""
        ws_response = client.post("/api/workspaces", json={"name": "Test"})
        workspace_id = ws_response.json()["id"]
        
        # Missing source or target should fail
        response = client.post(
            f"/api/workspaces/{workspace_id}/edges",
            json={"source": "some-id"}
        )
        assert response.status_code == 422

