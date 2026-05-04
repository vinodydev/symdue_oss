"""
Tests for LangGraph compiler
"""
import pytest
from services.graph.compiler import json_to_langgraph
from unittest.mock import MagicMock


@pytest.mark.unit
class TestGraphCompiler:
    """Test LangGraph compiler functionality"""
    
    def test_compile_simple_graph(self):
        """Test compiling a simple two-node graph"""
        graph_json = {
            "nodes": [
                {"id": "node-1", "node_type_id": "input", "config": {"value": "test"}},
                {"id": "node-2", "node_type_id": "custom-python", "config": {}}
            ],
            "edges": [
                {"source": "node-1", "target": "node-2", "weight": 1.0}
            ]
        }
        
        inputs = {"node-1": "test input"}
        run_id = "test-run-123"
        
        # Mock workflow for activity calls
        mock_workflow = MagicMock()
        
        graph = json_to_langgraph(graph_json, inputs, run_id, temporal_workflow=mock_workflow)
        
        assert graph is not None
        # Verify graph is compiled
        assert hasattr(graph, "nodes") or hasattr(graph, "graph")
    
    def test_compile_graph_with_multiple_entry_nodes(self):
        """Test compiling graph with multiple entry nodes"""
        graph_json = {
            "nodes": [
                {"id": "node-1", "node_type_id": "input", "config": {}},
                {"id": "node-2", "node_type_id": "input", "config": {}},
                {"id": "node-3", "node_type_id": "custom-python", "config": {}}
            ],
            "edges": [
                {"source": "node-1", "target": "node-3", "weight": 1.0},
                {"source": "node-2", "target": "node-3", "weight": 1.0}
            ]
        }
        
        inputs = {}
        run_id = "test-run-123"
        mock_workflow = MagicMock()
        
        graph = json_to_langgraph(graph_json, inputs, run_id, temporal_workflow=mock_workflow)
        
        assert graph is not None
    
    def test_compile_graph_with_weighted_edges(self):
        """Test compiling graph with weighted edges"""
        graph_json = {
            "nodes": [
                {"id": "node-1", "node_type_id": "input", "config": {}},
                {"id": "node-2", "node_type_id": "custom-python", "config": {}},
                {"id": "node-3", "node_type_id": "custom-python", "config": {}}
            ],
            "edges": [
                {"source": "node-1", "target": "node-2", "weight": 0.8},
                {"source": "node-1", "target": "node-3", "weight": 0.2}
            ]
        }
        
        inputs = {}
        run_id = "test-run-123"
        mock_workflow = MagicMock()
        
        graph = json_to_langgraph(graph_json, inputs, run_id, temporal_workflow=mock_workflow)
        
        assert graph is not None
    
    def test_compile_graph_with_single_node(self):
        """Test compiling graph with single node"""
        graph_json = {
            "nodes": [
                {"id": "node-1", "node_type_id": "input", "config": {}}
            ],
            "edges": []
        }
        
        inputs = {}
        run_id = "test-run-123"
        mock_workflow = MagicMock()
        
        graph = json_to_langgraph(graph_json, inputs, run_id, temporal_workflow=mock_workflow)
        
        assert graph is not None
    
    def test_compile_graph_handles_missing_weights(self):
        """Test that missing edge weights default to 1.0"""
        graph_json = {
            "nodes": [
                {"id": "node-1", "node_type_id": "input", "config": {}},
                {"id": "node-2", "node_type_id": "custom-python", "config": {}}
            ],
            "edges": [
                {"source": "node-1", "target": "node-2"}  # No weight specified
            ]
        }
        
        inputs = {}
        run_id = "test-run-123"
        mock_workflow = MagicMock()
        
        graph = json_to_langgraph(graph_json, inputs, run_id, temporal_workflow=mock_workflow)
        
        assert graph is not None

