"""
Tests for graph builder service
"""
import pytest
from uuid import uuid4
from services.workspace.graph_builder import build_graph_json
from database.models import Workflow, WorkflowNode, WorkflowEdge


@pytest.mark.integration
class TestGraphBuilder:
    """Test graph builder functionality"""
    
    def test_build_graph_json_simple(self, test_db):
        """Test building graph JSON from database"""
        # Create workflow
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create nodes
        node1 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="input",
            ui_x=100,
            ui_y=100,
            config={"value": "test"}
        )
        node2 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="custom-python",
            ui_x=300,
            ui_y=100,
            config={}
        )
        test_db.add(node1)
        test_db.add(node2)
        test_db.commit()
        
        # Create edge
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node2.id,
            weight=1.0
        )
        test_db.add(edge)
        test_db.commit()
        
        # Build graph JSON
        graph_json = build_graph_json(workflow.id, test_db)
        
        assert "nodes" in graph_json
        assert "edges" in graph_json
        assert len(graph_json["nodes"]) == 2
        assert len(graph_json["edges"]) == 1
        
        # Verify node structure
        node_ids = [n["id"] for n in graph_json["nodes"]]
        assert str(node1.id) in node_ids
        assert str(node2.id) in node_ids
        
        # Verify edge structure
        assert graph_json["edges"][0]["source"] == str(node1.id)
        assert graph_json["edges"][0]["target"] == str(node2.id)
        assert graph_json["edges"][0]["weight"] == 1.0
    
    def test_build_graph_json_with_weighted_edges(self, test_db):
        """Test building graph with weighted edges"""
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create nodes
        node1 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="input",
            ui_x=100,
            ui_y=100,
            config={}
        )
        node2 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="custom-python",
            ui_x=300,
            ui_y=100,
            config={}
        )
        node3 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="custom-python",
            ui_x=300,
            ui_y=200,
            config={}
        )
        test_db.add_all([node1, node2, node3])
        test_db.commit()
        
        # Create weighted edges
        edge1 = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node2.id,
            weight=0.8
        )
        edge2 = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node3.id,
            weight=0.2
        )
        test_db.add_all([edge1, edge2])
        test_db.commit()
        
        # Build graph JSON
        graph_json = build_graph_json(workflow.id, test_db)
        
        assert len(graph_json["edges"]) == 2
        weights = [e["weight"] for e in graph_json["edges"]]
        assert 0.8 in weights
        assert 0.2 in weights
    
    def test_build_graph_json_empty_workflow(self, test_db):
        """Test building graph for empty workflow"""
        workflow = Workflow(name="Empty Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        graph_json = build_graph_json(workflow.id, test_db)
        
        assert graph_json["nodes"] == []
        assert graph_json["edges"] == []
    
    def test_build_graph_json_excludes_deleted(self, test_db):
        """Test that deleted nodes/edges are excluded"""
        from sqlalchemy.sql import func
        
        workflow = Workflow(name="Test Workflow")
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Create nodes
        node1 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="input",
            ui_x=100,
            ui_y=100,
            config={}
        )
        node2 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="custom-python",
            ui_x=300,
            ui_y=100,
            config={},
            deleted_at=func.now()  # Soft delete
        )
        test_db.add_all([node1, node2])
        test_db.commit()
        
        # Build graph JSON
        graph_json = build_graph_json(workflow.id, test_db)
        
        # Should only include non-deleted node
        assert len(graph_json["nodes"]) == 1
        assert str(node1.id) in [n["id"] for n in graph_json["nodes"]]

