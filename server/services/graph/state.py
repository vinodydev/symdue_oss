"""
LangGraph state schema with Annotated reducers for concurrent updates.

Using a TypedDict with reducers allows parallel nodes to safely update
shared dict keys (node_outputs, node_inputs, node_name_map) without
triggering ``InvalidUpdateError`` during ``astream``.

``StateGraph(dict)`` wraps everything under a single ``__root__`` key,
which cannot receive two values in the same super-step.  With a proper
TypedDict each key is tracked independently and Annotated reducers
merge concurrent writes.
"""
from typing import Any, Dict, List, Annotated, TypedDict

def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow-merge two dicts; *right* wins on key conflicts."""
    merged = dict(left)
    merged.update(right)
    return merged


def take_max_step(left: Any, right: Any) -> int:
    """Reducer for _step_count: take max so parallel nodes don't trigger InvalidUpdateError."""
    l = left if isinstance(left, int) else 0
    r = right if isinstance(right, int) else 0
    return max(l, r)


def replace_list(left: Any, right: Any) -> Any:
    """Reducer for _resume_after_waits: right wins (replace semantics)."""
    return right if right is not None else left


def merge_dict_lists(
    left: Dict[str, List[Any]], right: Dict[str, List[Any]]
) -> Dict[str, List[Any]]:
    """Per-key list-append reducer for `node_iteration_outputs`.

    Each node call writes ``{node_id: [entry]}`` and this reducer appends
    onto the prior list rather than overwriting it. That preserves a
    per-iteration history across loop passes — see issue7/issue9.
    """
    out: Dict[str, List[Any]] = dict(left or {})
    for k, v in (right or {}).items():
        prev = out.get(k) or []
        if not isinstance(prev, list):
            prev = [prev]
        new = v if isinstance(v, list) else [v]
        out[k] = list(prev) + list(new)
    return out


def merge_dict_dicts(
    left: Dict[str, Dict[str, str]],
    right: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    """Per-key dict-merge reducer for `_node_consumed_inputs` (issue15).

    Each outer key is a node_id; the inner dict is
    ``{predecessor_id: sha256_hex_of_last_consumed_value}``.
    On conflict, right wins per inner key.
    """
    out: Dict[str, Dict[str, str]] = dict(left or {})
    for k, v in (right or {}).items():
        prev = out.get(k) or {}
        if not isinstance(prev, dict):
            prev = {}
        merged = dict(prev)
        if isinstance(v, dict):
            merged.update(v)
        out[k] = merged
    return out


class GraphState(TypedDict, total=False):
    inputs: Dict[str, Any]
    node_outputs: Annotated[Dict[str, Any], merge_dicts]
    node_inputs: Annotated[Dict[str, Any], merge_dicts]
    node_name_map: Annotated[Dict[str, Any], merge_dicts]
    # Append-only per-call history: one list entry per node execution.
    # Used to inspect intermediate iterations of looping nodes — see issue9.
    # Each entry is {"step": int, "ts": int, "output": <output_entry>}.
    node_iteration_outputs: Annotated[Dict[str, List[Any]], merge_dict_lists]
    # Per-node memo of last-consumed predecessor values (issue15).
    # Keyed node_id -> {predecessor_id -> sha256_hex_of_consumed_value}. Used
    # by node_function's skip-if-done check: a node re-fires only when at
    # least one predecessor's hash differs from what was last consumed.
    _node_consumed_inputs: Annotated[Dict[str, Dict[str, str]], merge_dict_dicts]
    run_id: str
    # Loop support: incremented after each node execution; used for max-steps guard and optional resume/UI.
    # Annotated so parallel nodes can both update step count without InvalidUpdateError.
    _step_count: Annotated[int, take_max_step]
    # Resume from non-saved node (Phase 2): when set, compiler uses resume entry to jump to this node.
    _resume_next_node: str
    # Wait node resume: list of node IDs to use as resume entry points after waits are satisfied.
    _resume_after_waits: Annotated[List[str], replace_list]
