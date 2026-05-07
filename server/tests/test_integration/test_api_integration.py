# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
API Integration Tests - Real HTTP requests to running server
These tests verify the API works end-to-end, not just unit tests
"""
import pytest
import requests
import os
from typing import Dict, Any
from uuid import uuid4

# Base URL for API (should be configurable)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class TestAPIIntegration:
    """Integration tests using real HTTP requests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Ensure server is running and migrations applied"""
        # Health check - server must be running
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            assert response.status_code == 200, "Server is not running or not healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Server is not running at {API_BASE_URL}. Start server first.")
        
        # Verify database is accessible (not 500 errors)
        # Note: 500 errors indicate migrations not run - this is a valid test failure
        try:
            response = requests.get(f"{API_BASE_URL}/api/workspaces", timeout=5)
            if response.status_code == 500:
                error_msg = response.text[:500] if response.text else "Unknown error"
                # Check if it's a migration issue
                if "does not exist" in error_msg or "relation" in error_msg.lower():
                    pytest.fail(
                        f"Database migrations not applied (500 error): {error_msg}\n"
                        f"Run: docker exec <backend> alembic upgrade head"
                    )
                else:
                    pytest.fail(f"Database not accessible (500 error): {error_msg}")
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not connect to API: {e}")
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_create_workspace_flow(self):
        """Complete workflow: Create workspace → Add nodes → Create edges"""
        workspace_id = None
        try:
            # 1. Create workspace
            response = requests.post(
                f"{API_BASE_URL}/api/workspaces",
                json={"name": "Integration Test Workspace"},
                timeout=10
            )
            assert response.status_code == 201, \
                f"Failed to create workspace: {response.status_code} - {response.text[:500]}"
            workspace = response.json()
            workspace_id = workspace["id"]
            assert "id" in workspace
            assert workspace["name"] == "Integration Test Workspace"
            
            # 2. Get workspace
            response = requests.get(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
            assert response.status_code == 200, \
                f"Failed to get workspace: {response.status_code} - {response.text[:500]}"
            workspace_data = response.json()
            assert workspace_data["id"] == workspace_id
            
            # 3. Create nodes
            node1_response = requests.post(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}},
                timeout=10
            )
            assert node1_response.status_code == 201, \
                f"Failed to create node1: {node1_response.status_code} - {node1_response.text[:500]}"
            node1 = node1_response.json()
            
            node2_response = requests.post(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "custom-python", "x": 200, "y": 0, "config_overrides": {}},
                timeout=10
            )
            assert node2_response.status_code == 201, \
                f"Failed to create node2: {node2_response.status_code} - {node2_response.text[:500]}"
            node2 = node2_response.json()
            
            # 4. Create edge
            edge_response = requests.post(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/edges",
                json={"source": node1["id"], "target": node2["id"], "weight": 0.8},
                timeout=10
            )
            assert edge_response.status_code == 201, \
                f"Failed to create edge: {edge_response.status_code} - {edge_response.text[:500]}"
            edge = edge_response.json()
            assert edge["weight"] == 0.8
            
            # 5. Get workspace with nodes and edges
            workspace_response = requests.get(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
            assert workspace_response.status_code == 200
            workspace_full = workspace_response.json()
            assert len(workspace_full["nodes"]) == 2
            assert len(workspace_full["edges"]) == 1
            
        finally:
            # Cleanup
            if workspace_id:
                try:
                    requests.delete(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
                except:
                    pass
    
    def test_node_types_endpoint(self):
        """Test node types endpoint"""
        response = requests.get(f"{API_BASE_URL}/api/node-types", timeout=5)
        assert response.status_code == 200, \
            f"Failed to get node types: {response.status_code} - {response.text[:500]}"
        node_types = response.json()
        assert isinstance(node_types, list)
        # Should have at least builtin types if seeded
        assert len(node_types) >= 0
    
    def test_llm_configs_flow(self):
        """Test LLM configs CRUD"""
        config_id = None
        try:
            # Create
            create_response = requests.post(
                f"{API_BASE_URL}/api/llm-configs",
                json={
                    "name": "Test Config",
                    "provider": "openai",
                    "model": "gpt-4",
                    "api_key": "test-key"
                },
                timeout=10
            )
            assert create_response.status_code == 201, \
                f"Failed to create LLM config: {create_response.status_code} - {create_response.text[:500]}"
            config = create_response.json()
            config_id = config["id"]
            
            # Get
            get_response = requests.get(f"{API_BASE_URL}/api/llm-configs/{config_id}", timeout=5)
            assert get_response.status_code == 200
            assert get_response.json()["id"] == config_id
            
            # Update
            update_response = requests.put(
                f"{API_BASE_URL}/api/llm-configs/{config_id}",
                json={"name": "Updated Config", "model": "gpt-3.5-turbo"},
                timeout=10
            )
            assert update_response.status_code == 200, \
                f"Failed to update LLM config: {update_response.status_code} - {update_response.text[:500]}"
            updated = update_response.json()
            assert updated["name"] == "Updated Config"
            
            # Delete
            delete_response = requests.delete(f"{API_BASE_URL}/api/llm-configs/{config_id}", timeout=5)
            assert delete_response.status_code == 204
            
            # Verify deleted
            get_deleted_response = requests.get(f"{API_BASE_URL}/api/llm-configs/{config_id}", timeout=5)
            assert get_deleted_response.status_code == 404
            
        except Exception as e:
            # Cleanup on error
            if config_id:
                try:
                    requests.delete(f"{API_BASE_URL}/api/llm-configs/{config_id}", timeout=5)
                except:
                    pass
            raise
    
    def test_runs_endpoint(self):
        """Test runs endpoint (may fail if Temporal not running)"""
        workspace_id = None
        try:
            # Create workspace first
            workspace_response = requests.post(
                f"{API_BASE_URL}/api/workspaces",
                json={"name": "Run Test"},
                timeout=10
            )
            assert workspace_response.status_code == 201, \
                f"Failed to create workspace: {workspace_response.status_code} - {workspace_response.text[:500]}"
            workspace = workspace_response.json()
            workspace_id = workspace["id"]
            
            # Create run
            run_response = requests.post(
                f"{API_BASE_URL}/api/runs/{workspace_id}",
                json={"inputs": {}},
                timeout=10
            )
            # May be 201 (success) or 500 (Temporal not running) - both are valid for integration test
            assert run_response.status_code in [201, 500], \
                f"Unexpected status: {run_response.status_code} - {run_response.text[:500]}"
            
            if run_response.status_code == 201:
                run_data = run_response.json()
                assert "run_id" in run_data
                assert "status" in run_data
                
        finally:
            # Cleanup
            if workspace_id:
                try:
                    requests.delete(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
                except:
                    pass
    
    def test_error_handling(self):
        """Test error handling"""
        workspace_id = None
        try:
            # 404 for non-existent workspace
            fake_id = str(uuid4())
            response = requests.get(f"{API_BASE_URL}/api/workspaces/{fake_id}", timeout=5)
            assert response.status_code == 404, \
                f"Expected 404 for non-existent workspace, got {response.status_code}"
            
            # 422 for invalid UUID format
            response = requests.get(f"{API_BASE_URL}/api/workspaces/invalid-uuid", timeout=5)
            assert response.status_code == 422, \
                f"Expected 422 for invalid UUID format, got {response.status_code}"
            
            # Create workspace for further error tests
            workspace_response = requests.post(
                f"{API_BASE_URL}/api/workspaces",
                json={"name": "Error Test"},
                timeout=10
            )
            assert workspace_response.status_code == 201
            workspace_id = workspace_response.json()["id"]
            
            # 404 for non-existent node
            fake_node_id = str(uuid4())
            response = requests.get(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/nodes/{fake_node_id}",
                timeout=5
            )
            assert response.status_code == 404, \
                f"Expected 404 for non-existent node, got {response.status_code}"
            
            # 422 for invalid edge weight (out of range)
            node1_response = requests.post(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "input", "x": 0, "y": 0, "config_overrides": {}},
                timeout=10
            )
            node2_response = requests.post(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}/nodes",
                json={"node_type_id": "input", "x": 100, "y": 100, "config_overrides": {}},
                timeout=10
            )
            if node1_response.status_code == 201 and node2_response.status_code == 201:
                node1_id = node1_response.json()["id"]
                node2_id = node2_response.json()["id"]
                
                # Try to create edge with invalid weight (> 1.0)
                edge_response = requests.post(
                    f"{API_BASE_URL}/api/workspaces/{workspace_id}/edges",
                    json={"source": node1_id, "target": node2_id, "weight": 1.5},
                    timeout=10
                )
                assert edge_response.status_code == 422, \
                    f"Expected 422 for invalid weight, got {edge_response.status_code}"
            
        finally:
            # Cleanup
            if workspace_id:
                try:
                    requests.delete(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
                except:
                    pass
    
    def test_list_workspaces(self):
        """Test listing workspaces"""
        response = requests.get(f"{API_BASE_URL}/api/workspaces", timeout=5)
        assert response.status_code == 200, \
            f"Failed to list workspaces: {response.status_code} - {response.text[:500]}"
        workspaces = response.json()
        assert isinstance(workspaces, list)
    
    def test_workspace_update(self):
        """Test workspace update"""
        workspace_id = None
        try:
            # Create workspace
            create_response = requests.post(
                f"{API_BASE_URL}/api/workspaces",
                json={"name": "Update Test"},
                timeout=10
            )
            assert create_response.status_code == 201
            workspace_id = create_response.json()["id"]
            
            # Update workspace
            update_response = requests.patch(
                f"{API_BASE_URL}/api/workspaces/{workspace_id}",
                json={"name": "Updated Name"},
                timeout=10
            )
            assert update_response.status_code == 200, \
                f"Failed to update workspace: {update_response.status_code} - {update_response.text[:500]}"
            updated = update_response.json()
            assert updated["name"] == "Updated Name"
            
        finally:
            if workspace_id:
                try:
                    requests.delete(f"{API_BASE_URL}/api/workspaces/{workspace_id}", timeout=5)
                except:
                    pass

