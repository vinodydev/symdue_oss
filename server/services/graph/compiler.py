"""
LangGraph compiler — converts a JSON graph structure to a compiled
LangGraph ``StateGraph`` ready for ``ainvoke()``.

Handles:
- Single and multiple entry points
- Single and weighted (conditional) edges
- Condition nodes (true/false branches; only matching branch runs)
- Terminal nodes (auto-connected to END)
- Parallel fan-out via weighted routing
- Loop support: cycle-aware entry nodes; optional resume entry when _resume_next_node is set
"""
import logging
from typing import Dict, Any, List, Optional

from langgraph.graph import StateGraph, END
from services.graph.state import GraphState
from services.graph.weighted_router import create_weighted_router, create_condition_router
from services.graph.graph_analysis import has_cycle, get_entry_nodes_with_forward_edges_only

logger = logging.getLogger(__name__)


def _is_condition_node(source_id: str, edges: List[Dict[str, Any]], node_map: Dict[str, Dict]) -> bool:
    """A node is a condition node if it is Python with condition_mode or condition-python, and has out-edges with source_handle."""
    node = node_map.get(source_id)
    if not node:
        return False
    ntype = node.get("node_type_id")
    config = node.get("config") or {}
    is_condition_type = ntype == "condition-python" or (ntype == "custom-python" and config.get("condition_mode") is True)
    if not is_condition_type:
        return False
    handles = {e.get("source_handle") for e in edges if e.get("source_handle") in ("true", "false")}
    return bool(handles)


def json_to_langgraph(
    graph_json: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    temporal_workflow=None,
    workflow_id: str = None,
    initial_state: Optional[Dict[str, Any]] = None,
    execution_config: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Convert graph JSON to a compiled LangGraph ``StateGraph``.

    Parameters
    ----------
    graph_json : dict
        ``{"nodes": [...], "edges": [...]}``
    inputs : dict
        Map of input-node-id → user-supplied value.
    run_id : str
        Run history ID (for tracking).
    temporal_workflow : optional
        If provided, node functions dispatch via Temporal activities.
        If ``None``, node functions call executors directly (used when
        we are already inside a Temporal activity).

    Returns
    -------
    Compiled LangGraph (callable via ``await graph.ainvoke(state)``).
    """
    from services.temporal.activities.node_executor import create_node_function

    workflow = StateGraph(GraphState)

    node_ids = {node["id"] for node in graph_json["nodes"]}
    logger.info(f"[run={run_id}] Compiling graph: {len(node_ids)} nodes")

    # ── Build edge map (grouped by source) ──
    # Only include edges where both source and target exist in the node set
    # Preserve source_handle for condition nodes
    node_map = {node["id"]: node for node in graph_json["nodes"]}
    edge_map: Dict[str, List[Dict[str, Any]]] = {}
    for edge in graph_json["edges"]:
        source = edge["source"]
        target = edge["target"]
        if source not in node_ids or target not in node_ids:
            logger.warning(
                f"[run={run_id}] Skipping stale edge {source[:8]}→{target[:8]}"
            )
            continue
        entry = {
            "target": target,
            "weight": edge.get("weight", 1.0),
        }
        if edge.get("source_handle") in ("true", "false"):
            entry["source_handle"] = edge["source_handle"]
        edge_map.setdefault(source, []).append(entry)

    # ── Add nodes ──
    graph_has_cycles = has_cycle(graph_json)
    is_resume = bool(initial_state and isinstance(initial_state, dict) and initial_state.get("node_outputs"))
    from config.settings import get_settings
    max_steps = get_settings().max_graph_steps
    for node_data in graph_json["nodes"]:
        node_func = create_node_function(
            node_data, run_id, inputs,
            workflow=temporal_workflow, workflow_id=workflow_id, graph_json=graph_json,
            has_cycles=graph_has_cycles, is_resume=is_resume, max_steps=max_steps,
            execution_config=execution_config,
        )
        workflow.add_node(node_data["id"], node_func)

    # ── Add edges ──
    for source_id, edges in edge_map.items():
        if _is_condition_node(source_id, edges, node_map):
            # Condition node: partition by source_handle; only matching branch runs
            true_targets = [e["target"] for e in edges if e.get("source_handle") == "true"]
            false_targets = [e["target"] for e in edges if e.get("source_handle") == "false"]
            target_map = {t: t for t in true_targets + false_targets}
            target_map["__end__"] = END
            router = create_condition_router(source_id, true_targets, false_targets)
            workflow.add_conditional_edges(source_id, router, target_map)
        elif len(edges) == 1:
            workflow.add_edge(source_id, edges[0]["target"])
        else:
            router = create_weighted_router(source_id, edges)
            target_map = {e["target"]: e["target"] for e in edges}
            workflow.add_conditional_edges(source_id, router, target_map)

    # ── Identify entry nodes ──
    # For cyclic graphs, use only forward edges so back-edges don't hide the real entry set.
    entry_nodes = get_entry_nodes_with_forward_edges_only(graph_json, edge_map)

    # ── Resume entry (Wait nodes): when _resume_after_waits is set, fan-out from synthetic node ──
    resume_after_waits = None
    if initial_state and isinstance(initial_state, dict):
        raw = initial_state.get("_resume_after_waits")
        if isinstance(raw, list) and raw:
            # Only keep IDs that actually exist in this graph
            resume_after_waits = [nid for nid in raw if nid in node_ids]

    if resume_after_waits:
        # Wait node resume: fan-out from synthetic start to all resume entry nodes
        resume_wait_id = f"_resume_wait_{run_id[:8]}"
        def _resume_wait_node(state: Dict[str, Any]) -> Dict[str, Any]:
            return {}
        workflow.add_node(resume_wait_id, _resume_wait_node)
        for target_id in resume_after_waits:
            workflow.add_edge(resume_wait_id, target_id)
        workflow.set_entry_point(resume_wait_id)
        logger.info(f"[run={run_id}] Graph compiled with wait resume entry -> {resume_after_waits}")
    else:
        # ── Resume entry (Phase 2): when graph has cycles and we're resuming, start from _resume_next_node ──
        resume_next = None
        if initial_state and isinstance(initial_state, dict):
            resume_next = initial_state.get("_resume_next_node")
        if isinstance(resume_next, str) and resume_next and resume_next in node_ids and has_cycle(graph_json):
            # Add synthetic _resume node as single entry; it routes to resume_next or to normal entries
            resume_id = f"_resume_{run_id[:8]}"
            def _resume_node(state: Dict[str, Any]) -> Dict[str, Any]:
                return {}
            workflow.add_node(resume_id, _resume_node)
            # Router: if _resume_next_node is set, go there; else go to normal entry (we'll add edges below)
            def _resume_router(state: Dict[str, Any]) -> str:
                n = state.get("_resume_next_node")
                if isinstance(n, str) and n in node_ids:
                    return n
                return "__default_entry__"
            # We need one real node as default; use first entry node
            default_entry = entry_nodes[0] if entry_nodes else next(iter(node_ids))
            workflow.add_conditional_edges(
                resume_id,
                _resume_router,
                {nid: nid for nid in node_ids} | {"__default_entry__": default_entry},
            )
            workflow.set_entry_point(resume_id)
            logger.info(f"[run={run_id}] Graph compiled with resume entry -> {resume_next}")
        elif len(entry_nodes) == 1:
            workflow.set_entry_point(entry_nodes[0])
        else:
            # Multiple entry points — fan out from a synthetic start node
            start_id = f"_start_{run_id[:8]}"
            workflow.add_node(start_id, lambda state: {})
            for entry in entry_nodes:
                workflow.add_edge(start_id, entry)
            workflow.set_entry_point(start_id)

    # ── Identify terminal nodes (no outgoing edges) → connect to END ──
    source_nodes = set(edge_map.keys())
    terminal_nodes = [nid for nid in node_ids if nid not in source_nodes]

    for term_id in terminal_nodes:
        workflow.add_edge(term_id, END)

    logger.info(
        f"[run={run_id}] Graph compiled: entries={entry_nodes}, "
        f"terminals={terminal_nodes}"
    )

    return workflow.compile()
