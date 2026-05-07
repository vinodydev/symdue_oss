# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for issue15 — per-edge value-change detection in the AND-join gate.

A node should re-fire only when at least one inbound predecessor's value
has changed since the last firing. This unifies DAG and cyclic-graph
semantics: pure-DAG nodes skip on subsequent calls (already-ran), cyclic
nodes re-fire only when their back-edge inbound delivers a fresh value.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch


# ──────────────────────────────────────────────────────────────────
# Reducer tests — merge_dict_dicts
# ──────────────────────────────────────────────────────────────────

def test_merge_dict_dicts_merges_per_inner_key():
    from services.graph.state import merge_dict_dicts
    left = {"a": {"x": "h1", "y": "h2"}}
    right = {"a": {"y": "H2", "z": "h3"}, "b": {"k": "h4"}}
    out = merge_dict_dicts(left, right)
    assert out["a"] == {"x": "h1", "y": "H2", "z": "h3"}
    assert out["b"] == {"k": "h4"}


def test_merge_dict_dicts_handles_empty_inputs():
    from services.graph.state import merge_dict_dicts
    assert merge_dict_dicts({}, {}) == {}
    assert merge_dict_dicts(None, None) == {}
    assert merge_dict_dicts({"x": {"a": "1"}}, None) == {"x": {"a": "1"}}
    assert merge_dict_dicts(None, {"x": {"a": "1"}}) == {"x": {"a": "1"}}


def test_hash_value_stable_across_equivalent_dicts():
    from services.temporal.activities.node_executor import _hash_value
    a = {"k1": "v", "k2": [1, 2, 3]}
    b = {"k2": [1, 2, 3], "k1": "v"}  # different insertion order
    assert _hash_value(a) == _hash_value(b)


def test_hash_value_different_for_different_data():
    from services.temporal.activities.node_executor import _hash_value
    assert _hash_value({"a": 1}) != _hash_value({"a": 2})
    assert _hash_value("hello") != _hash_value("world")


# ──────────────────────────────────────────────────────────────────
# Skip-if-done logic — node-function level
# ──────────────────────────────────────────────────────────────────

GRAPH_LINEAR = {
    "nodes": [
        {"id": "a", "node_type_id": "custom-python", "name": "A", "config": {}},
        {"id": "b", "node_type_id": "custom-python", "name": "B", "config": {}},
    ],
    "edges": [
        {"source": "a", "target": "b"},
    ],
}


def _make_node_function(graph_json, node_id):
    from services.temporal.activities.node_executor import create_node_function
    node_data = next(n for n in graph_json["nodes"] if n["id"] == node_id)
    return create_node_function(
        node_data,
        run_id="test-run",
        inputs={},
        workflow=None,
        workflow_id="test-wf",
        graph_json=graph_json,
        has_cycles=False,
    )


class _AggregatorCalled(Exception):
    """Sentinel: raised from the patched aggregator if we reach the run path."""


@pytest.mark.asyncio
async def test_first_call_always_runs():
    """First call: no prior _node_consumed_inputs entry — must run."""
    from services.temporal.activities.node_executor import _hash_value

    fn = _make_node_function(GRAPH_LINEAR, "b")
    a_value = {"output": "first"}
    state = {
        "node_outputs": {"a": a_value},
        # No _node_consumed_inputs[b] yet → first call.
    }
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_AggregatorCalled(),
    ):
        with pytest.raises(_AggregatorCalled):
            await fn(state)


@pytest.mark.asyncio
async def test_skip_when_inputs_unchanged():
    """Second call: B already has output AND A's hash matches what B last
    consumed → skip-if-done returns the empty diff."""
    from services.temporal.activities.node_executor import _hash_value

    fn = _make_node_function(GRAPH_LINEAR, "b")
    a_value = {"output": "first"}
    a_hash = _hash_value(a_value)
    state = {
        "node_outputs": {
            "a": a_value,
            "b": {"output": "computed"},  # B already ran
        },
        "_node_consumed_inputs": {"b": {"a": a_hash}},  # B last consumed a_value
    }
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_AggregatorCalled(),
    ) as agg_mock:
        result = await fn(state)
        agg_mock.assert_not_called()
    assert result == {"node_name_map": {"b": "B"}}


@pytest.mark.asyncio
async def test_refire_when_predecessor_changes():
    """Same setup as above but A's value changed → must re-fire."""
    from services.temporal.activities.node_executor import _hash_value

    fn = _make_node_function(GRAPH_LINEAR, "b")
    old_a = {"output": "first"}
    new_a = {"output": "updated"}
    state = {
        "node_outputs": {
            "a": new_a,                       # A's value updated
            "b": {"output": "computed"},
        },
        "_node_consumed_inputs": {"b": {"a": _hash_value(old_a)}},  # B last saw old A
    }
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_AggregatorCalled(),
    ):
        with pytest.raises(_AggregatorCalled):
            await fn(state)


@pytest.mark.asyncio
async def test_skip_persists_when_no_predecessors_at_all():
    """An entry node (no predecessors) with existing output should skip on
    subsequent re-evaluation — current_input_hashes is empty, last_consumed
    is also empty, but we treat 'no predecessors' as 'inputs unchanged' once
    we have output."""
    from services.temporal.activities.node_executor import _hash_value

    # Use a graph where node 'a' has no edges → no predecessors.
    no_edges_graph = dict(GRAPH_LINEAR, edges=[])
    fn = _make_node_function(no_edges_graph, "a")

    # Case 1: first call — runs.
    state_first = {"node_outputs": {}}
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_AggregatorCalled(),
    ):
        with pytest.raises(_AggregatorCalled):
            await fn(state_first)

    # Case 2: second call — already has output, no predecessors → skip.
    # Marker: "already consumed empty inputs" → presence of entry signals "ran."
    state_second = {
        "node_outputs": {"a": {"output": "ran"}},
        "_node_consumed_inputs": {"a": {}},   # ran with no predecessors before
    }
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_AggregatorCalled(),
    ) as agg_mock:
        result = await fn(state_second)
        agg_mock.assert_not_called()
    assert result == {"node_name_map": {"a": "A"}}
