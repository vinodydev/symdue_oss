# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for issue9: per-iteration node-output history.

Validates:
- The `merge_dict_lists` reducer appends correctly across diffs.
- Each successful node-function call writes to `node_iteration_outputs`.
- The history accumulates across multiple calls (loop iterations).
"""
import pytest
from unittest.mock import patch, AsyncMock


# ──────────────────────────────────────────────────────────────────
# Reducer-only tests (no LangGraph required)
# ──────────────────────────────────────────────────────────────────

def test_merge_dict_lists_appends_per_key():
    from services.graph.state import merge_dict_lists

    left = {"a": [{"step": 1}, {"step": 2}]}
    right = {"a": [{"step": 3}], "b": [{"step": 1}]}
    out = merge_dict_lists(left, right)
    assert out["a"] == [{"step": 1}, {"step": 2}, {"step": 3}]
    assert out["b"] == [{"step": 1}]


def test_merge_dict_lists_handles_empty_inputs():
    from services.graph.state import merge_dict_lists
    assert merge_dict_lists({}, {}) == {}
    assert merge_dict_lists(None, None) == {}
    assert merge_dict_lists({"x": [1]}, None) == {"x": [1]}
    assert merge_dict_lists(None, {"x": [1]}) == {"x": [1]}


def test_merge_dict_lists_promotes_scalar_to_list():
    """Defensive: if a node accidentally writes a scalar instead of a [scalar] list,
    the reducer should still produce a flat list."""
    from services.graph.state import merge_dict_lists
    out = merge_dict_lists({"a": "first"}, {"a": "second"})
    assert out["a"] == ["first", "second"]


# ──────────────────────────────────────────────────────────────────
# Node-function level tests (verify the write path includes the new field)
# ──────────────────────────────────────────────────────────────────

GRAPH_LINEAR = {
    "nodes": [
        {"id": "a", "node_type_id": "custom-python", "name": "A", "config": {}},
    ],
    "edges": [],
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


@pytest.mark.asyncio
async def test_node_function_writes_iteration_output():
    """A successful node call returns a diff that includes node_iteration_outputs[node_id]
    as a single-element list."""
    fn = _make_node_function(GRAPH_LINEAR, "a")

    # Stub the python-node activity so the function reaches its return branch.
    fake_result = {"output": "done"}
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        return_value={},
    ), patch(
        "services.temporal.activities.node_executor.execute_python_node_activity",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = await fn({"node_outputs": {}})

    assert "node_iteration_outputs" in result, (
        f"diff missing iteration history: {list(result.keys())}"
    )
    history = result["node_iteration_outputs"]
    assert "a" in history, history
    assert isinstance(history["a"], list) and len(history["a"]) == 1
    entry = history["a"][0]
    assert set(entry.keys()) >= {"step", "ts", "output"}
    assert entry["output"]["output"] == "done"
    assert entry["step"] == 1


@pytest.mark.asyncio
async def test_iteration_history_accumulates_across_calls():
    """Two successive calls produce two entries when fed through the reducer."""
    from services.graph.state import merge_dict_lists

    fn = _make_node_function(GRAPH_LINEAR, "a")
    accumulated_history: dict = {}

    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        return_value={},
    ), patch(
        "services.temporal.activities.node_executor.execute_python_node_activity",
        new_callable=AsyncMock,
        side_effect=[{"output": "iter0"}, {"output": "iter1"}, {"output": "iter2"}],
    ):
        for i in range(3):
            # Simulate state where step_count is i (not 0) so each call writes step i+1
            state = {"node_outputs": {}, "_step_count": i}
            diff = await fn(state)
            accumulated_history = merge_dict_lists(
                accumulated_history, diff.get("node_iteration_outputs") or {}
            )

    assert "a" in accumulated_history
    history = accumulated_history["a"]
    assert len(history) == 3, f"expected 3 entries, got {len(history)}: {history}"
    assert [e["output"]["output"] for e in history] == ["iter0", "iter1", "iter2"]
    assert [e["step"] for e in history] == [1, 2, 3]
