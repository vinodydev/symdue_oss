"""
Database operations and data persistence tests
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database.models import Workflow, WorkflowNode, WorkflowEdge
from main import app

client = TestClient(app)


class TestDatabaseOperations:
    """Test database is storing data properly"""
    
    def test_create_workspace_persists(self, test_db: Session):
        """Test workspace creation persists to database"""
        response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        assert response.status_code == 201
        workspace_id = response.json()["id"]
        
        # Verify in database
        workspace = test_db.query(Workflow).filter(Workflow.id == workspace_id).first()
        assert workspace is not None
        assert workspace.name == "Test Workspace"
        assert workspace.deleted_at is None
        assert workspace.transform == {"x": 0, "y": 0, "k": 1}
    
    def test_create_node_persists(self, test_db: Session):
        """Test node creation persists to database"""
        # Create workspace first
        ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
        workspace_id = ws_response.json()["id"]
        
        # Create node
        node_response = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={
                "node_type_id": "input",
                "x": 100.0,
                "y": 200.0,
                "config_overrides": {"name": "Test Node"}
            }
        )
        assert node_response.status_code == 201
        node_id = node_response.json()["id"]
        
        # Verify in database
        node = test_db.query(WorkflowNode).filter(WorkflowNode.id == node_id).first()
        assert node is not None
        assert node.node_type_id == "input"
        assert node.ui_x == 100.0
        assert node.ui_y == 200.0
        # Config includes default values from node type + overrides
        assert "name" in node.config
        assert node.config["name"] == "Test Node"
        assert node.deleted_at is None
    
    def test_create_edge_persists(self, test_db: Session):
        """Test edge creation persists to database"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test WS"})
        workspace_id = ws_response.json()["id"]
        
        # Create two nodes
        node1_response = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 0, "y": 0}
        )
        node2_response = client.post(
            f"/api/workspaces/{workspace_id}/nodes",
            json={"node_type_id": "input", "x": 100, "y": 100}
        )
        node1_id = node1_response.json()["id"]
        node2_id = node2_response.json()["id"]
        
        # Create edge
        edge_response = client.post(
            f"/api/workspaces/{workspace_id}/edges",
            json={
                "source": node1_id,
                "target": node2_id,
                "weight": 0.75
            }
        )
        assert edge_response.status_code == 201
        edge_id = edge_response.json()["id"]
        
        # Verify in database
        edge = test_db.query(WorkflowEdge).filter(WorkflowEdge.id == edge_id).first()
        assert edge is not None
        assert edge.weight == 0.75
        assert str(edge.source_node_id) == node1_id
        assert str(edge.target_node_id) == node2_id
        assert edge.deleted_at is None
    
    def test_soft_delete_workspace(self, test_db: Session):
        """Test soft delete sets deleted_at timestamp"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "To Delete"})
        workspace_id = ws_response.json()["id"]
        
        # Delete workspace
        delete_response = client.delete(f"/api/workspaces/{workspace_id}")
        assert delete_response.status_code == 204
        
        # Verify soft deleted in database
        workspace = test_db.query(Workflow).filter(Workflow.id == workspace_id).first()
        assert workspace is not None
        assert workspace.deleted_at is not None
    
    def test_restore_workspace(self, test_db: Session):
        """Test restore clears deleted_at timestamp"""
        # Create and delete workspace
        ws_response = client.post("/api/workspaces", json={"name": "To Restore"})
        workspace_id = ws_response.json()["id"]
        client.delete(f"/api/workspaces/{workspace_id}")
        
        # Restore workspace
        restore_response = client.post(f"/api/workspaces/{workspace_id}/restore")
        assert restore_response.status_code == 200
        
        # Verify restored in database
        workspace = test_db.query(Workflow).filter(Workflow.id == workspace_id).first()
        assert workspace is not None
        assert workspace.deleted_at is None

