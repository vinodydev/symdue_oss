"""
Tests for weighted router
"""
import pytest
from services.graph.weighted_router import create_weighted_router


@pytest.mark.unit
class TestWeightedRouter:
    """Test weighted routing logic"""
    
    def test_single_edge_routing(self):
        """Test routing with single edge"""
        edges = [{"target": "node-2", "weight": 1.0}]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        # Single edge with weight 1.0 returns list (parallel execution)
        assert isinstance(result, list)
        assert "node-2" in result
    
    def test_all_weights_one_parallel(self):
        """Test that all weights = 1.0 routes to all targets"""
        edges = [
            {"target": "node-2", "weight": 1.0},
            {"target": "node-3", "weight": 1.0}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        assert isinstance(result, list)
        assert "node-2" in result
        assert "node-3" in result
    
    def test_high_weight_routing(self):
        """Test routing to high-weight edge"""
        edges = [
            {"target": "node-2", "weight": 0.8},
            {"target": "node-3", "weight": 0.2}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        assert result == "node-2"
    
    def test_multiple_high_weights_parallel(self):
        """Test multiple high-weight edges execute in parallel"""
        edges = [
            {"target": "node-2", "weight": 0.8},
            {"target": "node-3", "weight": 0.75},
            {"target": "node-4", "weight": 0.2}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        assert isinstance(result, list)
        assert "node-2" in result
        assert "node-3" in result
        assert "node-4" not in result
    
    def test_zero_weight_edges_filtered(self):
        """Test that zero-weight edges are filtered out"""
        edges = [
            {"target": "node-2", "weight": 0.0},
            {"target": "node-3", "weight": 0.5}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        assert result == "node-3"
    
    def test_medium_weights_probability_based(self):
        """Test medium weights use probability-based routing"""
        edges = [
            {"target": "node-2", "weight": 0.4},
            {"target": "node-3", "weight": 0.6}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        result = router(state)
        
        # Should route to highest probability (node-3)
        assert result == "node-3"
    
    def test_all_zero_weights_raises_error(self):
        """Test that all zero-weight edges raise error"""
        edges = [
            {"target": "node-2", "weight": 0.0},
            {"target": "node-3", "weight": 0.0}
        ]
        router = create_weighted_router("node-1", edges)
        
        state = {"node_outputs": {}}
        
        with pytest.raises(ValueError):
            router(state)

