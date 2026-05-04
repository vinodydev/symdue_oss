"""
Tests for workflow config API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from database.connection import SessionLocal
from database.models import Workflow
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
def test_workflow(test_db):
    """Create a test workflow"""
    workflow = Workflow(name="Test Workflow for Config")
    test_db.add(workflow)
    test_db.commit()
    test_db.refresh(workflow)
    yield workflow
    test_db.delete(workflow)
    test_db.commit()


def test_update_workflow_config(test_workflow):
    """Test updating workflow config"""
    workflow_id = str(test_workflow.id)
    
    response = client.put(
        f"/api/workspaces/{workflow_id}/config",
        json={
            "config": {
                "S3_BUCKET": "my-bucket",
                "DATABASE_URL": "postgresql://localhost/test",
                "API_KEY": "test-key-123"
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == workflow_id
    assert data["config"]["S3_BUCKET"] == "my-bucket"
    assert data["config"]["DATABASE_URL"] == "postgresql://localhost/test"
    assert data["config"]["API_KEY"] == "test-key-123"


def test_get_workflow_config(test_workflow):
    """Test getting workflow config"""
    workflow_id = str(test_workflow.id)
    
    # First set config
    client.put(
        f"/api/workspaces/{workflow_id}/config",
        json={
            "config": {
                "S3_BUCKET": "test-bucket",
                "API_KEY": "key123"
            }
        }
    )
    
    # Then get it
    response = client.get(f"/api/workspaces/{workflow_id}/config")
    
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == workflow_id
    assert data["config"]["S3_BUCKET"] == "test-bucket"
    assert data["config"]["API_KEY"] == "key123"


def test_get_workflow_config_empty(test_workflow):
    """Test getting workflow config when none is set"""
    workflow_id = str(test_workflow.id)
    
    response = client.get(f"/api/workspaces/{workflow_id}/config")
    
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == workflow_id
    assert data["config"] == {}


def test_update_workflow_config_not_found():
    """Test updating config for non-existent workflow"""
    fake_id = str(uuid.uuid4())
    
    response = client.put(
        f"/api/workspaces/{fake_id}/config",
        json={"config": {"TEST": "value"}}
    )
    
    assert response.status_code == 404


def test_get_workflow_config_not_found():
    """Test getting config for non-existent workflow"""
    fake_id = str(uuid.uuid4())
    
    response = client.get(f"/api/workspaces/{fake_id}/config")
    
    assert response.status_code == 404

