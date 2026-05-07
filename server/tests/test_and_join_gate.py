# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for the AND-join gate in node_executor.py (issue7).

The gate must:
- Block a node from running until ALL its forward-edge predecessors have output.
- Ignore back-edges so cyclic graphs still progress on first iteration.
- Be a no-op for nodes with no forward predecessors (entry nodes).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ──────────────────────────────────────────────────────────────────────
# Pure-function reference test: confirms LangGraph 1.x StateGraph in fact
# multi-fires a multi-parent node when its inbound channels resolve at
# different super-steps. This is the behavior the gate exists to suppress.
# ──────────────────────────────────────────────────────────────────────

def test_langgraph_multi_inbound_baseline_misbehavior():
    """Documents the LangGraph behavior that motivates the AND-join gate."""
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Annotated, List
    import operator

    class S(TypedDict, total=False):
        log: Annotated[List[str], operator.add]

    g = StateGraph(S)

    def trace(name):
        def f(s):
            return {"log": [name]}

        return f

    for n in ["START", "RES", "A", "B"]:
        g.add_node(n, trace(n))
    g.add_edge("START", "RES")
    g.add_conditional_edges("RES", lambda s: ["A", "B"], {"A": "A", "B": "B"})
    # B has TWO inbound channels: one via the router from RES, one direct from A.
    # They resolve in different super-steps, so B fires twice.
    g.add_edge("A", "B")
    g.add_edge("B", END)
    g.set_entry_point("START")

    import asyncio
    out = asyncio.run(g.compile().ainvoke({}))
    # Without the gate, B fires twice. This is the bug the gate prevents
    # at the flowgraph node-function layer.
    assert out["log"].count("B") == 2, (
        f"Expected baseline LangGraph behavior to fire B twice; got {out['log']}"
    )


# ──────────────────────────────────────────────────────────────────────
# Gate behavior tests via create_node_function
# ──────────────────────────────────────────────────────────────────────

GRAPH_JSON_LINEAR = {
    "nodes": [
        {"id": "a", "node_type_id": "custom-python", "name": "A", "config": {}},
        {"id": "b", "node_type_id": "custom-python", "name": "B", "config": {}},
        {"id": "c", "node_type_id": "custom-python", "name": "C", "config": {}},
    ],
    "edges": [
        {"source": "a", "target": "c"},
        {"source": "b", "target": "c"},
    ],
}

GRAPH_JSON_CYCLIC = {
    # A → B → C, with a back-edge C → B.  When B is gated, the gate must
    # NOT wait on C's output (back-edge) — only on A's (forward).
    "nodes": [
        {"id": "a", "node_type_id": "custom-python", "name": "A", "config": {}},
        {"id": "b", "node_type_id": "custom-python", "name": "B", "config": {}},
        {"id": "c", "node_type_id": "condition-python", "name": "C", "config": {"condition_mode": True}},
    ],
    "edges": [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "b"},  # back-edge
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
        has_cycles=any(
            e["source"] in {n["id"] for n in graph_json["nodes"]}
            and e["target"] in {n["id"] for n in graph_json["nodes"]}
            for e in graph_json["edges"]
        ),
    )


@pytest.mark.asyncio
async def test_gate_blocks_when_one_forward_predecessor_missing():
    """C has forward predecessors {a, b}; only a has output → C must NOT execute."""
    fn = _make_node_function(GRAPH_JSON_LINEAR, "c")
    state = {"node_outputs": {"a": {"output": "x"}}}  # b missing

    # Patch the actual node-execution path so a real run would be visible.
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs"
    ) as agg_mock:
        result = await fn(state)
        # Gate fired → aggregator should NOT have been called.
        agg_mock.assert_not_called()
    # Empty-diff shape: only name_map, no node_outputs.
    assert result == {"node_name_map": {"c": "C"}}


class _GateCleared(Exception):
    """Sentinel: thrown from a mocked aggregator to prove the gate let us past it."""


@pytest.mark.asyncio
async def test_gate_clears_when_all_forward_predecessors_present():
    """C has forward predecessors {a, b}; both have output → gate clears."""
    fn = _make_node_function(GRAPH_JSON_LINEAR, "c")
    state = {
        "node_outputs": {
            "a": {"output": "x"},
            "b": {"output": "y"},
        }
    }
    # Make the aggregator throw a sentinel so we know the gate let us through
    # without having to mock the entire executor stack (Temporal/Docker/etc.).
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_GateCleared(),
    ):
        with pytest.raises(_GateCleared):
            await fn(state)


@pytest.mark.asyncio
async def test_gate_ignores_back_edges_so_loops_can_start():
    """B has inbound from A (forward) and C (back-edge). On iteration 0 only A
    has run; the gate must NOT wait on C, which is a back-edge."""
    fn = _make_node_function(GRAPH_JSON_CYCLIC, "b")
    state = {"node_outputs": {"a": {"output": "seed"}}}  # only A; C hasn't run yet

    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_GateCleared(),
    ):
        with pytest.raises(_GateCleared):
            await fn(state)


@pytest.mark.asyncio
async def test_gate_is_noop_for_entry_node():
    """A has no inbound edges; gate must not block entry nodes."""
    fn = _make_node_function(GRAPH_JSON_LINEAR, "a")
    state = {"node_outputs": {}}

    # Entry-node "input" type goes through a different input-building branch
    # (sets node_inputs from `inputs` arg), not via _aggregate_node_inputs.
    # So we can't use the same sentinel pattern. Use a fresh graph_json where
    # 'a' is a custom-python node, and verify the aggregator is called.
    graph = dict(GRAPH_JSON_LINEAR, edges=[])  # remove all edges → 'a' has no inbounds
    fn = _make_node_function(graph, "a")
    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_GateCleared(),
    ):
        with pytest.raises(_GateCleared):
            await fn(state)


# ──────────────────────────────────────────────────────────────────────
# Issue 11 — multi-path-into-cycle
# Reproduces the DEEP_RESEARCH topology (simplified) where the graph has
# both a "shortcut" cross-SCC edge AND an in-cycle non-back-edge into the
# same node. Earlier gate (DFS-from-true-entry) misclassified the in-cycle
# edge as a back-edge depending on UUID sort order, letting the node fire
# on the shortcut alone with phantom data. The SCC + condition-mode rule
# fixes this.
# ──────────────────────────────────────────────────────────────────────

# Topology:
#   ENTRY (input) → JOIN  (shortcut, cross-SCC)
#   ENTRY → COMPUTE → COND (condition node) → JOIN (in-cycle non-back-edge)
#                       └────[back-edge]──→ COMPUTE
#
# JOIN has two inbounds: ENTRY (cross-SCC) and COND (same SCC as JOIN, since
# COND→JOIN→...→COND would form a cycle if JOIN→...→COND existed; for this
# reduced repro JOIN's only outbound is END, so COND→JOIN is the only edge
# in JOIN's SCC and is NOT a back-edge by reachability rules).
#
# The simplified test below sticks to a 4-node loop where the bug surfaces
# clearly: ENTRY → JOIN (direct shortcut), ENTRY → COMPUTE → JOIN (chain),
# JOIN → CHECK → COMPUTE (back-edge from condition node CHECK).

GRAPH_JSON_MULTIPATH_CYCLE = {
    "nodes": [
        {"id": "entry", "node_type_id": "custom-python", "name": "ENTRY", "config": {}},
        {"id": "compute", "node_type_id": "custom-python", "name": "COMPUTE", "config": {}},
        {"id": "join", "node_type_id": "custom-python", "name": "JOIN", "config": {}},
        {"id": "check", "node_type_id": "condition-python", "name": "CHECK", "config": {"condition_mode": True}},
    ],
    "edges": [
        {"source": "entry", "target": "join"},      # shortcut, cross-SCC
        {"source": "entry", "target": "compute"},
        {"source": "compute", "target": "join"},    # in-cycle non-back-edge
        {"source": "join", "target": "check"},
        {"source": "check", "target": "compute"},   # back-edge from condition node
    ],
}


@pytest.mark.asyncio
async def test_gate_waits_on_in_cycle_non_backedge_predecessor():
    """JOIN has predecessors {ENTRY, COMPUTE}. ENTRY is cross-SCC (forward).
    COMPUTE is in the same SCC as JOIN but is NOT a condition node — its edge
    must be treated as forward, not back-edge. With only ENTRY satisfied,
    JOIN should NOT fire."""
    fn = _make_node_function(GRAPH_JSON_MULTIPATH_CYCLE, "join")
    state = {"node_outputs": {"entry": {"output": "started"}}}

    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
    ) as agg_mock:
        result = await fn(state)
        agg_mock.assert_not_called()
    assert result == {"node_name_map": {"join": "JOIN"}}, (
        f"Gate should have blocked, got: {result}"
    )


@pytest.mark.asyncio
async def test_gate_clears_when_in_cycle_non_backedge_satisfied():
    """Same topology — but now COMPUTE has output too. Gate should clear."""
    fn = _make_node_function(GRAPH_JSON_MULTIPATH_CYCLE, "join")
    state = {
        "node_outputs": {
            "entry": {"output": "started"},
            "compute": {"output": "computed"},
        }
    }

    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_GateCleared(),
    ):
        with pytest.raises(_GateCleared):
            await fn(state)


@pytest.mark.asyncio
async def test_gate_skips_back_edge_from_condition_node():
    """COMPUTE has predecessors {ENTRY, CHECK}. ENTRY is cross-SCC (forward).
    CHECK is in the same SCC AND is condition-mode AND COMPUTE→...→CHECK
    forms a cycle (COMPUTE→JOIN→CHECK), so CHECK→COMPUTE is the back-edge —
    must be skipped so the loop can start. With only ENTRY satisfied, gate
    should clear."""
    fn = _make_node_function(GRAPH_JSON_MULTIPATH_CYCLE, "compute")
    state = {"node_outputs": {"entry": {"output": "started"}}}

    with patch(
        "services.temporal.activities.node_executor._aggregate_node_inputs",
        side_effect=_GateCleared(),
    ):
        with pytest.raises(_GateCleared):
            await fn(state)
