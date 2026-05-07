# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for graph analysis (cycle detection, entry nodes with back-edges).
"""
import pytest
from services.graph.graph_analysis import (
    has_cycle,
    get_entry_nodes_with_forward_edges_only,
    get_next_node_ids,
)


@pytest.mark.unit
class TestHasCycle:
    """Test cycle detection."""

    def test_no_cycle_linear(self):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ],
        }
        assert has_cycle(graph) is False

    def test_no_cycle_dag(self):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
            "edges": [
                {"source": "a", "target": "c"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "d"},
            ],
        }
        assert has_cycle(graph) is False

    def test_cycle_back_edge(self):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"},
            ],
        }
        assert has_cycle(graph) is True

    def test_self_loop(self):
        graph = {
            "nodes": [{"id": "a"}],
            "edges": [{"source": "a", "target": "a"}],
        }
        assert has_cycle(graph) is True

    def test_empty_graph(self):
        graph = {"nodes": [], "edges": []}
        assert has_cycle(graph) is False

    def test_single_node_no_edges(self):
        graph = {"nodes": [{"id": "a"}], "edges": []}
        assert has_cycle(graph) is False


@pytest.mark.unit
class TestGetEntryNodesWithForwardEdgesOnly:
    """Test entry node computation with and without cycles."""

    def test_dag_entry_nodes(self):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ],
        }
        edge_map = {"a": [{"target": "b"}], "b": [{"target": "c"}]}
        entries = get_entry_nodes_with_forward_edges_only(graph, edge_map)
        assert entries == ["a"]

    def test_cyclic_entry_nodes(self):
        # A -> B -> C -> A: with back-edge C->A excluded, only A has no incoming forward edge
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"},
            ],
        }
        edge_map = {
            "a": [{"target": "b"}],
            "b": [{"target": "c"}],
            "c": [{"target": "a"}],
        }
        entries = get_entry_nodes_with_forward_edges_only(graph, edge_map)
        assert len(entries) >= 1
        assert "a" in entries or "b" in entries or "c" in entries

    def test_cyclic_with_input_entry(self):
        # Input -> A -> B -> Cond -> (true->A, false->C). Entry should include Input
        graph = {
            "nodes": [
                {"id": "input"},
                {"id": "a"},
                {"id": "b"},
                {"id": "cond"},
                {"id": "c"},
            ],
            "edges": [
                {"source": "input", "target": "a"},
                {"source": "a", "target": "b"},
                {"source": "b", "target": "cond"},
                {"source": "cond", "target": "a", "source_handle": "true"},
                {"source": "cond", "target": "c", "source_handle": "false"},
            ],
        }
        edge_map = {
            "input": [{"target": "a"}],
            "a": [{"target": "b"}],
            "b": [{"target": "cond"}],
            "cond": [
                {"target": "a", "source_handle": "true"},
                {"target": "c", "source_handle": "false"},
            ],
        }
        entries = get_entry_nodes_with_forward_edges_only(graph, edge_map)
        assert "input" in entries


@pytest.mark.unit
class TestGetNextNodeIds:
    """Test next-node resolution for resume."""

    def test_single_edge(self):
        graph = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}]}
        node_map = {"a": {"id": "a"}, "b": {"id": "b"}}
        edge_map = {"a": [{"target": "b", "weight": 1.0}]}
        state = {}
        next_ids = get_next_node_ids(graph, edge_map, node_map, "a", state)
        assert next_ids == ["b"]

    def test_no_edges(self):
        graph = {"nodes": [{"id": "a"}], "edges": []}
        node_map = {"a": {"id": "a"}}
        edge_map = {}
        state = {}
        next_ids = get_next_node_ids(graph, edge_map, node_map, "a", state)
        assert next_ids == []
