# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for workflow export and import as JSON API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from database.models import Workflow, WorkflowNode, WorkflowEdge


@pytest.fixture
def client(test_db):
    """Test client with overridden get_db."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def workflow_with_nodes_edges(test_db):
    """Create a workflow with two nodes and one edge."""
    w = Workflow(name="Export Test", workflow_config={"KEY": "value"})
    test_db.add(w)
    test_db.commit()
    test_db.refresh(w)

    n1 = WorkflowNode(
        workflow_id=w.id,
        node_type_id="input",
        name="Input 1",
        ui_x=10.0,
        ui_y=20.0,
        config={"value": "x"},
        node_config={"NODE_VAR": "v"},
    )
    n2 = WorkflowNode(
        workflow_id=w.id,
        node_type_id="custom-python",
        name="Python 1",
        ui_x=100.0,
        ui_y=200.0,
        config={"code": "print(1)"},
        node_config={},
    )
    test_db.add(n1)
    test_db.add(n2)
    test_db.commit()
    test_db.refresh(n1)
    test_db.refresh(n2)

    e = WorkflowEdge(
        workflow_id=w.id,
        source_node_id=n1.id,
        target_node_id=n2.id,
        weight=0.8,
    )
    test_db.add(e)
    test_db.commit()

    yield w
    test_db.delete(e)
    test_db.delete(n1)
    test_db.delete(n2)
    test_db.delete(w)
    test_db.commit()


def test_export_workflow(client, workflow_with_nodes_edges):
    """Export returns 200 and valid JSON shape."""
    w = workflow_with_nodes_edges
    response = client.get(f"/api/workspaces/{w.id}/export")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 1
    assert data["name"] == "Export Test"
    assert data["workflow_config"] == {"KEY": "value"}
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    node_ids = {n["id"] for n in data["nodes"]}
    assert len(node_ids) == 2
    e = data["edges"][0]
    assert e["source_node_id"] in node_ids
    assert e["target_node_id"] in node_ids
    assert e["weight"] == 0.8
    for n in data["nodes"]:
        assert "node_type_id" in n
        assert "name" in n
        assert "ui_x" in n
        assert "ui_y" in n
        assert "config" in n


def test_export_workflow_not_found(client):
    """Export 404 for unknown workflow."""
    import uuid
    response = client.get(f"/api/workspaces/{uuid.uuid4()}/export")
    assert response.status_code == 404


def test_import_workflow_creates_new(client, test_db):
    """Import creates a new workflow with nodes and edges."""
    payload = {
        "version": 1,
        "name": "Imported Workflow",
        "transform": {"x": 0, "y": 0, "k": 1},
        "workflow_config": {"X": "y"},
        "nodes": [
            {
                "id": "n1",
                "name": "Input A",
                "node_type_id": "input",
                "ui_x": 0,
                "ui_y": 0,
                "config": {},
                "node_config": {},
            },
            {
                "id": "n2",
                "name": "Python B",
                "node_type_id": "custom-python",
                "ui_x": 50,
                "ui_y": 50,
                "config": {},
                "node_config": {},
            },
        ],
        "edges": [
            {"source_node_id": "n1", "target_node_id": "n2", "weight": 1.0},
        ],
    }
    response = client.post("/api/workspaces/import", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Imported Workflow"
    assert "id" in data
    wid = data["id"]
    detail = client.get(f"/api/workspaces/{wid}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert len(detail_data["nodes"]) == 2
    assert len(detail_data["edges"]) == 1
    assert detail_data["nodes"][0]["name"] == "Input A"
    assert detail_data["nodes"][1]["name"] == "Python B"
    assert detail_data["edges"][0]["weight"] == 1.0


def test_import_workflow_unknown_node_type(client):
    """Import with unknown node_type_id returns 400."""
    payload = {
        "version": 1,
        "name": "Bad",
        "nodes": [
            {
                "id": "n1",
                "name": "Bad Node",
                "node_type_id": "nonexistent-type-xyz",
                "ui_x": 0,
                "ui_y": 0,
                "config": {},
                "node_config": {},
            },
        ],
        "edges": [],
    }
    response = client.post("/api/workspaces/import", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "node_type_id" in detail.lower() or "unknown" in detail.lower()


def test_import_workflow_duplicate_node_id(client):
    """Import with duplicate node id returns 400."""
    payload = {
        "version": 1,
        "name": "Dup",
        "nodes": [
            {"id": "same", "name": "A", "node_type_id": "input", "ui_x": 0, "ui_y": 0, "config": {}, "node_config": {}},
            {"id": "same", "name": "B", "node_type_id": "input", "ui_x": 10, "ui_y": 10, "config": {}, "node_config": {}},
        ],
        "edges": [],
    }
    response = client.post("/api/workspaces/import", json=payload)
    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"].lower()


def test_import_workflow_edge_unknown_source(client):
    """Import with edge referencing unknown source node returns 400."""
    payload = {
        "version": 1,
        "name": "Bad Edge",
        "nodes": [
            {"id": "n1", "name": "Only", "node_type_id": "input", "ui_x": 0, "ui_y": 0, "config": {}, "node_config": {}},
        ],
        "edges": [{"source_node_id": "unknown-id", "target_node_id": "n1", "weight": 1.0}],
    }
    response = client.post("/api/workspaces/import", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "source" in detail.lower() or "unknown" in detail.lower()


def test_import_workflow_edge_unknown_target(client):
    """Import with edge referencing unknown target node returns 400."""
    payload = {
        "version": 1,
        "name": "Bad Edge",
        "nodes": [
            {"id": "n1", "name": "Only", "node_type_id": "input", "ui_x": 0, "ui_y": 0, "config": {}, "node_config": {}},
        ],
        "edges": [{"source_node_id": "n1", "target_node_id": "unknown-id", "weight": 1.0}],
    }
    response = client.post("/api/workspaces/import", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "target" in detail.lower() or "unknown" in detail.lower()


def test_export_import_roundtrip(client, workflow_with_nodes_edges):
    """Export then import produces a new workflow with same structure."""
    w = workflow_with_nodes_edges
    export_resp = client.get(f"/api/workspaces/{w.id}/export")
    assert export_resp.status_code == 200
    payload = export_resp.json()
    payload["name"] = "Roundtrip Copy"
    import_resp = client.post("/api/workspaces/import", json=payload)
    assert import_resp.status_code == 201
    new_data = import_resp.json()
    assert new_data["id"] != str(w.id)
    assert new_data["name"] == "Roundtrip Copy"
    detail = client.get(f"/api/workspaces/{new_data['id']}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert len(detail_data["nodes"]) == 2
    assert len(detail_data["edges"]) == 1
    names = {n["name"] for n in detail_data["nodes"]}
    assert "Input 1" in names
    assert "Python 1" in names
