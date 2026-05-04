"""
Tests for node config API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from database.connection import SessionLocal
from database.models import Workflow, WorkflowNode
import uuid

client = TestClient(app)


@pytest.fixture
def test_db():
    """Database session fixture"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_workflow_and_node(test_db):
    """Create a test workflow and node"""
    workflow = Workflow(name="Test Workflow for Node Config")
    test_db.add(workflow)
    test_db.commit()
    test_db.refresh(workflow)
    
    node = WorkflowNode(
        workflow_id=workflow.id,
        node_type_id="python",
        name="Test Node",
        ui_x=0.0,
        ui_y=0.0,
        config={}
    )
    test_db.add(node)
    test_db.commit()
    test_db.refresh(node)
    
    yield workflow, node
    
    test_db.delete(node)
    test_db.delete(workflow)
    test_db.commit()


def test_update_node_config(test_workflow_and_node):
    """Test updating node config"""
    workflow, node = test_workflow_and_node
    workflow_id = str(workflow.id)
    node_id = str(node.id)
    
    response = client.put(
        f"/api/workspaces/{workflow_id}/nodes/{node_id}/config",
        json={
            "node_config": {
                "NODE_TIMEOUT": "60",
                "NODE_RETRIES": "5",
                "NODE_CHECK_INTERVAL": "10"
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["node_id"] == node_id
    assert data["node_config"]["NODE_TIMEOUT"] == "60"
    assert data["node_config"]["NODE_RETRIES"] == "5"
    assert data["node_config"]["NODE_CHECK_INTERVAL"] == "10"


def test_update_node_config_not_found():
    """Test updating config for non-existent node"""
    fake_workflow_id = str(uuid.uuid4())
    fake_node_id = str(uuid.uuid4())
    
    response = client.put(
        f"/api/workspaces/{fake_workflow_id}/nodes/{fake_node_id}/config",
        json={"node_config": {"TEST": "value"}}
    )
    
    assert response.status_code == 404

