"""
Graph analysis utilities for loop support (back-edges / cycles).

Provides cycle detection, entry-node computation that ignores back-edges,
and next-node resolution for partial snapshot (resume).
"""
from typing import Dict, Any, List, Set, Tuple


def has_cycle(graph_json: Dict[str, Any]) -> bool:
    """
    Return True if the graph contains at least one cycle.

    Uses DFS with recursion stack. Input: graph_json with "nodes" and "edges".
    Edges are dicts with "source" and "target" (node IDs).
    """
    nodes = graph_json.get("nodes", [])
    edges = graph_json.get("edges", [])
    node_ids = {str(n["id"]) for n in nodes}
    if not node_ids:
        return False

    # Build adjacency list (outgoing)
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        src = str(e.get("source"))
        tgt = str(e.get("target"))
        if src in node_ids and tgt in node_ids:
            adj.setdefault(src, []).append(tgt)

    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def dfs(nid: str) -> bool:
        visited.add(nid)
        rec_stack.add(nid)
        for neighbor in adj.get(nid, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(nid)
        return False

    for nid in node_ids:
        if nid not in visited:
            if dfs(nid):
                return True
    return False


def _find_back_edges(
    node_ids: Set[str],
    edge_list: List[Dict[str, Any]],
) -> Set[Tuple[str, str]]:
    """
    Return set of (source, target) edges that are back-edges (part of a cycle).
    Uses DFS: an edge (u, v) is a back-edge iff v is in the recursion stack when we process u.
    """
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edge_list:
        src = str(e.get("source"))
        tgt = str(e.get("target"))
        if src in node_ids and tgt in node_ids:
            adj.setdefault(src, []).append(tgt)

    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    back_edges: Set[Tuple[str, str]] = set()

    def dfs(nid: str) -> None:
        visited.add(nid)
        rec_stack.add(nid)
        for neighbor in adj.get(nid, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                back_edges.add((nid, neighbor))
        rec_stack.remove(nid)

    for nid in node_ids:
        if nid not in visited:
            dfs(nid)
    return back_edges


def compute_sccs(graph_json: Dict[str, Any]) -> List[List[str]]:
    """
    Tarjan's strongly connected components algorithm — O(V+E).

    Returns a list of SCCs. Each SCC is a list of node IDs. Singleton SCCs
    (nodes not in any cycle) are returned as 1-element lists. Multi-element
    lists identify cyclic groups; every node in a multi-element SCC is
    reachable from every other node in that SCC.

    Used by the AND-join gate (issue11) to classify predecessor edges:
    edges between different SCCs are forward dependencies; edges within an
    SCC are cycle-internal and need additional rules (e.g. condition-mode
    convention) to decide whether to wait on them.
    """
    nodes = graph_json.get("nodes", []) or []
    edges = graph_json.get("edges", []) or []
    node_ids = [str(n["id"]) for n in nodes]
    node_set = set(node_ids)

    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        src = str(e.get("source"))
        tgt = str(e.get("target"))
        if src in node_set and tgt in node_set:
            adj[src].append(tgt)
    # Sort for deterministic output across runs.
    for k in adj:
        adj[k].sort()

    index_counter = [0]
    index_of: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    sccs: List[List[str]] = []

    def strongconnect(v: str) -> None:
        index_of[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in adj.get(v, []):
            if w not in index_of:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index_of[w])
        if lowlink[v] == index_of[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            sccs.append(sorted(scc))

    for nid in sorted(node_ids):
        if nid not in index_of:
            strongconnect(nid)

    return sccs


def get_entry_nodes_with_forward_edges_only(
    graph_json: Dict[str, Any],
    edge_map: Dict[str, List[Dict[str, Any]]],
) -> List[str]:
    """
    Compute entry nodes for the graph. When the graph has cycles, use only
    "forward" edges (exclude back-edges) so that nodes that are re-entered
    via a back-edge still qualify as entry nodes if they have no other
    incoming forward edge.

    Args:
        graph_json: Must have "nodes" and "edges".
        edge_map: Dict source_id -> list of edge dicts with "target" (and optionally "source_handle").
                  Must match graph_json (same edges, grouped by source).

    Returns:
        List of node IDs that are entry nodes. Never empty: falls back to first node if needed.
    """
    node_ids = {str(n["id"]) for n in graph_json["nodes"]}
    if not node_ids:
        return []

    edges_flat: List[Dict[str, Any]] = []
    for src, out_edges in edge_map.items():
        for e in out_edges:
            tgt = e.get("target")
            if tgt is not None and src in node_ids and tgt in node_ids:
                edges_flat.append({"source": src, "target": tgt})

    if not has_cycle(graph_json):
        # DAG: entry nodes = nodes with no incoming edge
        targets = {e["target"] for e in edges_flat}
        entry = [nid for nid in node_ids if nid not in targets]
        if entry:
            return sorted(entry)
        return [next(iter(node_ids))]

    # Cyclic: exclude back-edges, then entry = nodes with no incoming forward edge
    back = _find_back_edges(node_ids, edges_flat)
    forward_targets: Set[str] = set()
    for e in edges_flat:
        src, tgt = str(e.get("source")), str(e.get("target"))
        if (src, tgt) not in back:
            forward_targets.add(tgt)
    entry = [nid for nid in node_ids if nid not in forward_targets]
    if entry:
        return sorted(entry)
    return [next(iter(node_ids))]


def _is_condition_node_for_next(
    source_id: str, edges: List[Dict[str, Any]], node_map: Dict[str, Dict[str, Any]]
) -> bool:
    """Same condition-node detection as compiler (for next-node resolution)."""
    node = node_map.get(source_id)
    if not node:
        return False
    ntype = node.get("node_type_id")
    config = node.get("config") or {}
    is_condition_type = (
        ntype == "condition-python"
        or (ntype == "custom-python" and config.get("condition_mode") is True)
    )
    if not is_condition_type:
        return False
    handles = {e.get("source_handle") for e in edges if e.get("source_handle") in ("true", "false")}
    return bool(handles)


def get_next_node_ids(
    graph_json: Dict[str, Any],
    edge_map: Dict[str, List[Dict[str, Any]]],
    node_map: Dict[str, Dict[str, Any]],
    source_node_id: str,
    state: Dict[str, Any],
) -> List[str]:
    """
    Return the list of next node IDs that would be executed after source_node_id
    given the current state (mirrors compiler routing: condition, single edge, or weighted).

    Used for partial snapshot (resume) so we can store next_node_id.
    """
    from services.graph.weighted_router import (
        create_condition_router,
        create_weighted_router,
    )

    edges = edge_map.get(source_node_id, [])
    if not edges:
        return []

    node_ids = set(node_map.keys())
    if _is_condition_node_for_next(source_node_id, edges, node_map):
        true_targets = [e["target"] for e in edges if e.get("source_handle") == "true"]
        false_targets = [e["target"] for e in edges if e.get("source_handle") == "false"]
        router = create_condition_router(source_node_id, true_targets, false_targets)
        out = router(state)
        if out == "__end__":
            return []
        if isinstance(out, list):
            return [n for n in out if n in node_ids]
        return [out] if out in node_ids else []
    if len(edges) == 1:
        t = edges[0]["target"]
        return [t] if t in node_ids else []
    router = create_weighted_router(source_node_id, edges)
    out = router(state)
    if isinstance(out, list):
        return [n for n in out if n in node_ids]
    return [out] if out in node_ids else []
