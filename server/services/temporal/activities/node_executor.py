"""
Node execution activities (Temporal).

All heavy imports (langgraph, langchain, docker, etc.) happen here,
**not** inside the Temporal workflow (which runs in a sandbox).

Key activity:
  ``execute_graph_activity`` — compiles the JSON graph with LangGraph,
  executes it (one compile + one astream per graph), and publishes
  per-node status updates via Redis. LangGraph runs multiple times only
  when (1) a workflow_node runs a subworkflow (one full LangGraph run per
  child graph) or (2) Temporal retries the activity.
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from datetime import timedelta, datetime
from typing import Any, Callable, Dict, List, Optional


def _hash_value(v: Any) -> str:
    """Deterministic hash of any value for issue15's value-change detection.

    Tries JSON with ``sort_keys=True, default=str`` first; falls back to
    ``repr()`` for anything truly weird. SHA-256 hex digest.
    """
    try:
        return hashlib.sha256(
            json.dumps(v, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    except Exception:
        return hashlib.sha256(
            repr(v).encode("utf-8", errors="replace")
        ).hexdigest()

from temporalio import activity
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

# ─── Retry policy for node execution ───────────────────────
NODE_EXECUTION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
)


# ════════════════════════════════════════════════════════════
# Snapshot sanitization (issue12)
# Postgres jsonb rejects strings containing \x00 (NULL byte) and other
# unpaired Unicode surrogates with: psycopg2.errors.UntranslatableCharacter.
# LLM outputs occasionally contain such bytes (streaming artifacts, model
# tokenizer edge cases). Sanitize all strings before persistence.
# ════════════════════════════════════════════════════════════


def _sanitize_for_jsonb(obj: Any) -> Any:
    """
    Recursively strip characters that Postgres jsonb cannot store.

    Removes \x00 (NULL bytes) — the most common offender from LLM outputs.
    Returns a new object; does not mutate the input.
    """
    if isinstance(obj, str):
        if "\x00" in obj:
            return obj.replace("\x00", "")
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_jsonb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_jsonb(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize_for_jsonb(v) for v in obj)
    return obj


# ════════════════════════════════════════════════════════════
# Suspended state propagation support
# ════════════════════════════════════════════════════════════


def _has_suspended_input(state: Dict, node_id: str, graph_json: Dict) -> bool:
    """
    Return True if any upstream node of *node_id* has a __suspended__ output marker.
    Used so downstream nodes skip execution when a wait node is blocking them.
    """
    edges = graph_json.get("edges", [])
    node_outputs = state.get("node_outputs", {})
    for edge in edges:
        if str(edge.get("target")) == str(node_id):
            source_id = str(edge.get("source"))
            output = node_outputs.get(source_id)
            if isinstance(output, dict) and output.get("__suspended__"):
                return True
    return False


# ════════════════════════════════════════════════════════════
# Iterator support
# ════════════════════════════════════════════════════════════

def _should_use_iterator(node_config: Dict[str, Any]) -> bool:
    """Check if node should process inputs as an iterator."""
    iterator_config = node_config.get("iterator", {})
    return bool(iterator_config.get("enabled", False) and iterator_config.get("source_node_name"))


def _extract_array_from_output(source_output: Any, array_key: str) -> Any:
    """
    Extract array from source output using array_key path.
    
    Supports:
    - Simple key: "items" → source_output["items"]
    - Dot notation: "data.results" → source_output["data"]["results"]
    - Default: if array_key is "output" or not specified, try source_output["output"]
    
    Edge Cases Handled:
    - source_output is None → raises ValueError
    - array_key points to None → raises ValueError (None is not a valid array)
    - array_key points to non-list → wraps in array (intended behavior for single values)
    - Nested structures like {"output": {"output": [...]}} → handles correctly via dot notation
    
    Array Key Default Behavior (Precedence Order):
    When array_key is "output" or not specified:
    1. If source_output is a dict with "output" key → use source_output["output"]
    2. If source_output is already a list → use it directly
    3. If source_output is a dict without "output" key → wrap entire dict in array [source_output]
    4. If source_output is any other type → wrap in array [source_output]
    """
    if source_output is None:
        raise ValueError("Source output is None, cannot extract array")
    
    if array_key == "output" or not array_key:
        # Default behavior: check for "output" key or use directly if already array
        if isinstance(source_output, dict):
            if "output" in source_output:
                value = source_output["output"]
                if value is None:
                    raise ValueError("Array key 'output' points to None, which is not a valid array")
                if isinstance(value, list):
                    return value
                # If output is not array, wrap in single-item array (intended behavior)
                return [value]
            # Dict without "output" key → wrap entire dict in array
            return [source_output]
        elif isinstance(source_output, list):
            return source_output
        else:
            # Wrap single value in array (intended behavior)
            return [source_output]
    
    # Use dot notation to navigate
    if "." in array_key:
        parts = array_key.split(".")
        current = source_output
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                raise ValueError(f"Cannot access '{part}' from {type(current).__name__}")
            if current is None:
                raise ValueError(f"Key path '{array_key}' points to None, which is not a valid array")
        return current if isinstance(current, list) else [current]
    else:
        # Simple key access
        if isinstance(source_output, dict):
            value = source_output.get(array_key)
            if value is None:
                raise ValueError(f"Key '{array_key}' points to None, which is not a valid array")
            return value if isinstance(value, list) else [value]
        else:
            raise ValueError(f"Cannot access key '{array_key}' from {type(source_output).__name__}")


# ════════════════════════════════════════════════════════════
# LangGraph node-function factory (used by compiler)
# ════════════════════════════════════════════════════════════


def _merge_upstream_outputs_for_workflow_node(
    state: Dict[str, Any],
    workflow_node_id: str,
    graph_json: Dict[str, Any],
) -> Dict[str, Any]:
    """Build merged input dict from all nodes that have an edge into the workflow node. Each upstream output is normalized to a dict; merge (last wins)."""
    edges = graph_json.get("edges", [])
    node_outputs = state.get("node_outputs") or {}
    node_name_map = state.get("node_name_map") or {}
    sources = [str(e["source"]) for e in edges if str(e.get("target")) == str(workflow_node_id)]
    merged = {}
    for src_id in sources:
        out = node_outputs.get(src_id) or node_outputs.get(node_name_map.get(src_id, src_id))
        if out is None:
            continue
        if isinstance(out, dict) and "output" in out:
            val = out["output"]
        else:
            val = out
        if isinstance(val, dict):
            merged = {**merged, **val}
        else:
            # Single value: use source node name as key
            name = node_name_map.get(src_id, src_id)
            merged[name] = val
    return merged


async def _run_subworkflow(
    workflow_id: str,
    merged_inputs: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """
    Load child graph, run it with merged_inputs, return output dict keyed by output node names.
    Creates a RunHistory row for the child so the run appears in the child workflow's history.
    Returns {"output": {...}, "child_run_id": str, "child_workflow_id": str}.
    """
    from database.connection import SessionLocal
    from database.models import RunHistory
    from services.workspace.graph_builder import build_graph_json
    from uuid import UUID
    import uuid as uuid_module

    # Load graph with a short-lived session (do not hold across execution)
    db = SessionLocal()
    try:
        graph_json = build_graph_json(UUID(workflow_id), db)
    finally:
        db.close()

    if not graph_json.get("nodes"):
        return {"output": {}, "child_run_id": None, "child_workflow_id": str(workflow_id)}

    # Create child run record (short-lived session; commit and close before execution)
    child_run_id = uuid_module.uuid4()
    db_create = SessionLocal()
    try:
        child_run = RunHistory(
            id=child_run_id,
            workflow_id=UUID(workflow_id),
            parent_run_id=UUID(run_id),
            status="running",
            snapshot={},  # NOT NULL column; never None
            label="Sub-run (from parent)",
            temporal_workflow_id=None,
        )
        db_create.add(child_run)
        db_create.commit()
    except Exception as e:
        logger.exception(f"[run={run_id}] Failed to create child run for workflow {workflow_id}: {e}")
        db_create.rollback()
        db_create.close()
        raise
    finally:
        db_create.close()

    child_run_id_str = str(child_run_id)
    result_output = {}
    try:
        last_state = await _execute_with_langgraph(
            workflow_id, graph_json, merged_inputs, child_run_id_str, initial_state=None
        )
        # Build output dict from output nodes
        edges = graph_json.get("edges", [])
        source_ids = {str(e["source"]) for e in edges}
        node_ids = {str(n["id"]) for n in graph_json["nodes"]}
        output_node_ids = node_ids - source_ids
        node_outputs = last_state.get("node_outputs") or {}
        node_name_map = last_state.get("node_name_map") or {}
        for nid in output_node_ids:
            name = node_name_map.get(nid, nid)
            out = node_outputs.get(nid) or node_outputs.get(name)
            if isinstance(out, dict) and "output" in out:
                result_output[name] = out["output"]
            else:
                result_output[name] = out

        # Update child run on success (new session)
        _update_child_run_results(child_run_id_str, last_state, "success")
        return {
            "output": result_output,
            "child_run_id": child_run_id_str,
            "child_workflow_id": str(workflow_id),
        }
    except asyncio.CancelledError:
        # Child may have already called _persist_partial_state_on_cancel; preserve that snapshot
        db_cancel = SessionLocal()
        try:
            run = db_cancel.query(RunHistory).filter(RunHistory.id == child_run_id).first()
            if run:
                existing = (run.snapshot or {}) if isinstance(run.snapshot, dict) else {}
                existing_outputs = existing.get("node_outputs") or {}
                if not existing_outputs:
                    run.snapshot = {"error": "Activity cancelled", "error_type": "CancelledError", "node_outputs": {}}
                run.status = "cancelled"
                run.error_message = "Activity cancelled"
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                run.completed_at = now
                if run.started_at is not None:
                    run.duration = (now - run.started_at).total_seconds()
                db_cancel.commit()
        finally:
            db_cancel.close()
        raise
    except Exception as e:
        # Update child run with failed state
        partial = {
            "inputs": merged_inputs,
            "node_outputs": {},
            "node_name_map": {},
            "error": str(e),
            "error_type": type(e).__name__,
            "run_id": child_run_id_str,
            "workflow_id": workflow_id,
        }
        _update_child_run_results(child_run_id_str, partial, "error")
        raise


def _update_child_run_results(
    run_id: str,
    final_state: Dict[str, Any],
    status: str,
) -> None:
    """Update a run's snapshot, status, duration, and node stats. Preserves partial snapshot on cancel."""
    from database.connection import SessionLocal
    from database.models import RunHistory
    from datetime import datetime, timezone
    from uuid import UUID

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == UUID(run_id)).first()
        if not run:
            logger.warning(f"[run={run_id}] Run not found for update")
            return
        incoming_outputs = final_state.get("node_outputs") or {}
        existing_snapshot = (run.snapshot or {}) if isinstance(run.snapshot, dict) else {}
        existing_outputs = existing_snapshot.get("node_outputs") or {}
        preserve_partial = (
            status == "error"
            and not incoming_outputs
            and existing_outputs
        )
        if preserve_partial:
            run.status = "cancelled"
            run.error_message = final_state.get("error", "Activity cancelled")
            node_outputs = existing_outputs
            node_name_map = existing_snapshot.get("node_name_map") or {}
        else:
            run.status = status
            run.snapshot = _sanitize_for_jsonb(final_state)
            run.error_message = final_state.get("error")
            node_outputs = final_state.get("node_outputs", {})
            node_name_map = final_state.get("node_name_map") or {}

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run.completed_at = now
        if run.started_at is not None:
            run.duration = (now - run.started_at).total_seconds()

        name_values = set(node_name_map.values()) if node_name_map else set()
        unique_outputs = {k: v for k, v in node_outputs.items() if k not in name_values}
        run.total_nodes = len(unique_outputs)
        run.completed_nodes = sum(
            1 for v in unique_outputs.values()
            if not (isinstance(v, dict) and "error" in v)
        )
        run.failed_nodes = sum(
            1 for v in unique_outputs.values()
            if isinstance(v, dict) and "error" in v
        )
        db.commit()
    finally:
        db.close()


def create_node_function(
    node_data: Dict[str, Any],
    run_id: str,
    inputs: Dict[str, Any],
    workflow=None,
    workflow_id: Optional[str] = None,
    graph_json: Optional[Dict[str, Any]] = None,
    has_cycles: bool = False,
    is_resume: bool = False,
    max_steps: int = 1000,
    execution_config: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Return an async function suitable for ``StateGraph.add_node``.

    When *workflow* is provided (Temporal context), activities are
    dispatched via ``workflow.execute_activity``.  Otherwise they
    are called directly (useful for the ``execute_graph_activity``
    approach where we're already inside an activity).
    """
    cfg = execution_config or {}
    default_node_timeout = int(cfg.get("default_node_timeout_seconds", 600))
    node_id = node_data["id"]
    node_name = node_data.get("name", node_id)  # Fallback to ID if name missing
    node_type_id = node_data["node_type_id"]
    node_config = node_data.get("config", {})

    # ── Wait node handling ──────────────────────────────────────────────────
    if node_type_id == "wait":
        async def wait_node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            # If already resolved (signal payload present from resume), skip
            existing = state.get("node_outputs", {}).get(node_id)
            if existing and isinstance(existing, dict) and not existing.get("__suspended__"):
                return {"node_name_map": {node_id: node_name}}

            # Persist wait state to DB
            node_cfg = node_config or {}
            channel = node_cfg.get("channel", "")
            mode = node_cfg.get("mode", "signal")
            signals = node_cfg.get("signals") or []
            timeout_str = node_cfg.get("timeout")
            timeout_at = None
            if timeout_str:
                import re
                match = re.match(r"^(\d+)(m|h|s)$", str(timeout_str))
                if match:
                    val = int(match.group(1))
                    unit = match.group(2)
                    from datetime import timezone
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    delta = timedelta(
                        seconds=val if unit == "s" else val * 60 if unit == "m" else val * 3600
                    )
                    # Cap against max_wait_timeout_hours
                    from config.settings import get_settings
                    max_hours = get_settings().max_wait_timeout_hours
                    max_delta = timedelta(hours=max_hours)
                    if delta > max_delta:
                        delta = max_delta
                    timeout_at = now + delta

            try:
                from database.connection import SessionLocal
                from services.signals.wait_service import persist_wait_state
                db_wait = SessionLocal()
                try:
                    await persist_wait_state(
                        run_id=run_id,
                        node_id=node_id,
                        channel=channel,
                        mode=mode,
                        signals_needed=signals,
                        timeout_at=timeout_at,
                        db=db_wait,
                    )
                finally:
                    db_wait.close()
            except Exception as exc:
                logger.error(f"[run={run_id}] Failed to persist wait state for node={node_id}: {exc}")

            # Compute timeout_seconds for the Temporal wait_condition
            timeout_seconds = None
            if timeout_at:
                from datetime import timezone as tz
                remaining = (timeout_at - datetime.now(tz.utc).replace(tzinfo=None)).total_seconds()
                timeout_seconds = max(int(remaining), 1)

            suspended_entry = {
                "__suspended__": True,
                "channel": channel,
                "node_id": node_id,
                "timeout_seconds": timeout_seconds,
            }
            return {
                "node_outputs": {node_id: suspended_entry, node_name: suspended_entry},
                "node_name_map": {node_id: node_name},
            }
        return wait_node_function

    async def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
        # ── Suspended propagation: skip if an upstream wait node is blocking ──
        if graph_json and _has_suspended_input(state, node_id, graph_json):
            suspended_entry = {"__suspended__": True}
            return {
                "node_outputs": {node_id: suspended_entry, node_name: suspended_entry},
                "node_name_map": {node_id: node_name},
            }

        # ── AND-join gate: wait for all forward-edge predecessors to complete ──
        # See issue11 for the full design and rationale. The rule:
        #   For each predecessor edge (u, v) where v == this node:
        #     • If scc(u) != scc(v): forward edge — must wait.
        #     • If scc(u) == scc(v) AND u is condition-mode AND v is reachable
        #       from u: in-cycle back-edge from the loop's condition node — skip.
        #     • Otherwise: forward edge inside a cycle — must wait.
        #
        # This combines Tarjan's SCC (deterministic cycle membership) with
        # flowgraph's convention that loops close via condition-python nodes.
        # Replaces an earlier DFS-from-entry approach that was order-dependent
        # and could pick the wrong back-edge in multi-path-into-cycle graphs.
        if graph_json:
            from services.graph.graph_analysis import compute_sccs
            edges_list = graph_json.get("edges", []) or []
            nids = {str(n.get("id")) for n in (graph_json.get("nodes") or [])}
            sccs = compute_sccs(graph_json)
            node_to_scc = {n: i for i, scc in enumerate(sccs) for n in scc}
            # Build adjacency for reachability checks (only used for in-SCC edges
            # to confirm u→...→v exists, ruling out same-SCC edges that aren't
            # actually closing a cycle through us).
            adj_for_reach: Dict[str, List[str]] = {nid: [] for nid in nids}
            for e in edges_list:
                s = str(e.get("source")); t = str(e.get("target"))
                if s in nids and t in nids:
                    adj_for_reach[s].append(t)

            # Identify condition-mode nodes (loop closers by convention).
            cond_nodes: set = set()
            for n in (graph_json.get("nodes") or []):
                ntype = n.get("node_type_id")
                cfg = n.get("config") or {}
                if ntype == "condition-python" or (
                    ntype == "custom-python" and cfg.get("condition_mode") is True
                ):
                    cond_nodes.add(str(n.get("id")))

            def _reachable(src: str, dst: str) -> bool:
                """BFS from src; returns whether dst is reachable."""
                if src == dst:
                    return True
                seen = {src}
                queue = [src]
                while queue:
                    cur = queue.pop()
                    for nxt in adj_for_reach.get(cur, []):
                        if nxt == dst:
                            return True
                        if nxt not in seen:
                            seen.add(nxt)
                            queue.append(nxt)
                return False

            forward_preds: set = set()
            my_scc = node_to_scc.get(node_id)
            for e in edges_list:
                if str(e.get("target")) != node_id:
                    continue
                u = str(e.get("source"))
                if u not in nids or u == node_id:
                    continue
                if node_to_scc.get(u) != my_scc:
                    forward_preds.add(u)            # different SCC → forward
                # In same SCC: edge u→v is a back-edge iff v can reach u
                # (forming the cycle u→v→...→u). Combined with the convention
                # that loops close via condition-mode nodes, treat such edges
                # from condition nodes as back-edges to skip.
                elif u in cond_nodes and _reachable(node_id, u):
                    pass                            # in-cycle back-edge from condition node → skip
                else:
                    forward_preds.add(u)            # in-cycle non-back-edge → forward
            if forward_preds:
                outs = state.get("node_outputs") or {}
                missing = [p for p in forward_preds if p not in outs]
                if missing:
                    return {"node_name_map": {node_id: node_name}}

        # ── Skip-if-done with value-change detection (issue15) ──
        # A node re-fires only when at least one of its inbound predecessor
        # values has actually changed since its last firing. This unifies
        # DAG and cyclic-graph semantics — the old `has_cycles and not is_resume`
        # bypass is gone because the new criterion handles both cases:
        #   - DAG node, predecessors don't change after first fire → skip ✓
        #   - Cyclic node, back-edge fires with new value → re-fire ✓
        #   - Cyclic node, downstream updates state but predecessors unchanged → skip ✓
        # Hashes are recorded in `_node_consumed_inputs` after each successful run.
        all_predecessor_ids: List[str] = []
        if graph_json:
            _nids_for_preds = {
                str(n.get("id"))
                for n in (graph_json.get("nodes") or [])
            }
            for e in (graph_json.get("edges") or []):
                src = str(e.get("source"))
                tgt = str(e.get("target"))
                if tgt == node_id and src in _nids_for_preds and src != node_id:
                    all_predecessor_ids.append(src)
        current_input_hashes: Dict[str, str] = {
            p: _hash_value((state.get("node_outputs") or {}).get(p))
            for p in all_predecessor_ids
        }
        consumed_map = state.get("_node_consumed_inputs") or {}
        has_consumed_record = node_id in consumed_map
        last_consumed = consumed_map.get(node_id) or {}
        # First call (no record yet) → run. Otherwise compare hashes.
        # An entry-type node with no predecessors and an empty record skips
        # on subsequent calls — there's nothing that could have changed.
        inputs_changed = (not has_consumed_record) or any(
            current_input_hashes.get(p) != last_consumed.get(p)
            for p in all_predecessor_ids
        )
        existing = state.get("node_outputs", {}).get(node_id)
        if (
            existing
            and isinstance(existing, dict)
            and "error" not in existing
            and not existing.get("__suspended__")
            and not inputs_changed
        ):
            return {"node_name_map": {node_id: node_name}}

        # ── Step count and max-steps guard (loop support) ──
        step = (state.get("_step_count") or 0) + 1
        if step > max_steps:
            raise RuntimeError(
                f"Exceeded max steps ({max_steps}); possible infinite loop. "
                "Check your condition node or increase max_graph_steps."
            )

        # ── Build per-node inputs ──
        if node_type_id == "input":
            node_inputs = {"value": inputs.get(node_id, node_config.get("value", ""))}
        else:
            node_inputs = _aggregate_node_inputs(state, node_id, node_config)
        # Edge node: inject from parent/external input when "Use input from parent" is enabled
        if node_config.get("use_input_from_parent"):
            key = node_config.get("external_input_key") or node_name
            if key in inputs:
                node_inputs["value"] = inputs[key]

        # ── Check for iterator mode (after input aggregation, before type dispatch) ──
        if _should_use_iterator(node_config):
            if workflow:
                result = await workflow.execute_activity(
                    _process_with_iterator_activity,
                    args=[node_id, node_type_id, node_config, node_inputs, run_id, node_name, workflow_id],
                    start_to_close_timeout=timedelta(seconds=600),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await _process_with_iterator(
                    node_id, node_type_id, node_config, node_inputs, run_id, node_name, workflow_id
                )

            output = result.get("output", result)
            output_entry = {"output": output}
            if isinstance(result, dict) and result.get("logs"):
                output_entry["logs"] = result["logs"]
            if isinstance(result, dict) and result.get("error"):
                output_entry["error"] = result["error"]
            if isinstance(result, dict) and result.get("errors"):
                output_entry["errors"] = result["errors"]
            iter_entry = {"step": step, "ts": int(time.time()), "output": output_entry}
            return {
                "node_outputs": {node_id: output_entry, node_name: output_entry},
                "node_iteration_outputs": {node_id: [iter_entry]},
                "_node_consumed_inputs": {node_id: current_input_hashes},
                "node_inputs": {node_id: node_inputs},
                "node_name_map": {node_id: node_name},
                "_step_count": step,
            }

        # ── Dispatch by type ──
        if node_type_id == "input":
            if workflow:
                result = await workflow.execute_activity(
                    execute_input_node_activity,
                    args=[node_id, node_config, node_inputs, run_id],
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await execute_input_node_activity(node_id, node_config, node_inputs, run_id)

        elif node_type_id in ("custom-python", "condition-python"):
            if workflow:
                result = await workflow.execute_activity(
                    execute_python_node_activity,
                    args=[node_id, node_config, node_inputs, run_id, workflow_id, default_node_timeout],
                    start_to_close_timeout=timedelta(seconds=default_node_timeout),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await execute_python_node_activity(
                    node_id, node_config, node_inputs, run_id, workflow_id, timeout_seconds=default_node_timeout
                )

        elif node_type_id == "custom-llm":
            if workflow:
                result = await workflow.execute_activity(
                    execute_llm_node_activity,
                    args=[node_id, node_config, node_inputs, run_id],
                    start_to_close_timeout=timedelta(seconds=180),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await execute_llm_node_activity(node_id, node_config, node_inputs, run_id)

        elif node_type_id == "memory":
            if workflow:
                result = await workflow.execute_activity(
                    execute_memory_node_activity,
                    args=[node_id, node_config, node_inputs, run_id],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await execute_memory_node_activity(node_id, node_config, node_inputs, run_id)

        elif node_type_id == "html-viewer":
            if workflow:
                result = await workflow.execute_activity(
                    execute_html_viewer_node_activity,
                    args=[node_id, node_config, node_inputs, run_id],
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=NODE_EXECUTION_RETRY_POLICY,
                )
            else:
                result = await execute_html_viewer_node_activity(node_id, node_config, node_inputs, run_id)

        elif node_type_id == "workflow_node":
            # Sub-workflow: merge upstream outputs and run child graph
            ref_workflow_id = node_config.get("workflow_id")
            if not ref_workflow_id:
                raise ValueError("workflow_node missing config.workflow_id")
            merged_inputs = _merge_upstream_outputs_for_workflow_node(state, node_id, graph_json or {})
            await publish_node_status(run_id, node_id, "running")
            try:
                result = await _run_subworkflow(ref_workflow_id, merged_inputs, run_id)
                output_dict = result.get("output", {})
                child_run_id = result.get("child_run_id")
                child_workflow_id = result.get("child_workflow_id") or ref_workflow_id
                output_entry = {"output": output_dict}
                if child_run_id is not None:
                    output_entry["child_run_id"] = child_run_id
                    output_entry["child_workflow_id"] = child_workflow_id
                await publish_node_status(run_id, node_id, "success", {"output": output_dict})
                iter_entry = {"step": step, "ts": int(time.time()), "output": output_entry}
                return {
                    "node_outputs": {node_id: output_entry, node_name: output_entry},
                    "node_iteration_outputs": {node_id: [iter_entry]},
                    "_node_consumed_inputs": {node_id: current_input_hashes},
                    "node_inputs": {node_id: node_inputs},
                    "node_name_map": {node_id: node_name},
                    "_step_count": step,
                }
            except Exception as e:
                await publish_node_status(run_id, node_id, "error", {"error": {"type": type(e).__name__, "message": str(e)}})
                raise

        else:
            raise ValueError(f"Unknown node type: {node_type_id}")

        output = result.get("output", result)
        output_entry = {"output": output}
        if isinstance(result, dict) and result.get("logs"):
            output_entry["logs"] = result["logs"]
        if isinstance(result, dict) and result.get("error"):
            output_entry["error"] = result["error"]
        iter_entry = {"step": step, "ts": int(time.time()), "output": output_entry}
        return {
            "node_outputs": {node_id: output_entry, node_name: output_entry},
            "node_iteration_outputs": {node_id: [iter_entry]},
            "_node_consumed_inputs": {node_id: current_input_hashes},
            "node_inputs": {node_id: node_inputs},
            "node_name_map": {node_id: node_name},
            "_step_count": step,
        }

    return node_function


# ════════════════════════════════════════════════════════════
# Input aggregation
# ════════════════════════════════════════════════════════════

def _aggregate_node_inputs(
    state: Dict[str, Any],
    node_id: str,
    node_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Aggregate outputs from all upstream nodes into a dict keyed by **node name**.

    Every upstream node's output is stored under its human-readable name so
    that user code can do ``inputs["my_node_name"]`` instead of using UUIDs.

    For example, if upstream node "fetch_data" produced ``{"price": 42}``,
    the downstream node receives ``inputs["fetch_data"] == {"price": 42}``.

    Falls back to UUIDs if names are not available.
    Future enhancement: use edge weights to scale / filter inputs.
    """
    node_outputs = state.get("node_outputs", {})
    node_name_map = state.get("node_name_map", {})  # {node_id: node_name}
    aggregated: Dict[str, Any] = {}

    for source_id, output_entry in node_outputs.items():
        # Skip name-keyed entries (outputs are stored by both id and name)
        if source_id in node_name_map.values():
            continue

        # Always use node name as key — never flatten dicts
        source_name = node_name_map.get(source_id, source_id)

        # Extract the actual output value, stripping executor metadata (logs, error)
        # Node outputs are stored as {"output": <value>, "logs": ..., "error": ...}
        # but downstream nodes should only receive the raw output value.
        if isinstance(output_entry, dict) and "output" in output_entry:
            aggregated[source_name] = output_entry["output"]
        else:
            aggregated[source_name] = output_entry

    return aggregated


# ════════════════════════════════════════════════════════════
# Iterator processing
# ════════════════════════════════════════════════════════════

async def _process_with_iterator(
    node_id: str,
    node_type_id: str,
    node_config: Dict[str, Any],
    aggregated_inputs: Dict[str, Any],  # Already aggregated from _aggregate_node_inputs
    run_id: str,
    node_name: str,
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process node in iterator mode: iterate over array and process each item.
    
    IMPORTANT: This function receives already-aggregated inputs from _aggregate_node_inputs.
    The inputs dict is keyed by node names (not IDs).
    
    Args:
        node_id: Node ID
        node_type_id: Node type (custom-llm, custom-python, etc.)
        node_config: Node configuration (includes iterator config)
        aggregated_inputs: Already-aggregated inputs from _aggregate_node_inputs (keyed by node names)
        run_id: Run ID
        node_name: Node name (for progress tracking)
    
    Returns:
        {"output": [result1, result2, ...], "output_type": "array", "errors": [...], ...}
    """
    iterator_config = node_config.get("iterator", {})
    source_node_name = iterator_config.get("source_node_name")
    array_key = iterator_config.get("array_key", "output")
    error_strategy = iterator_config.get("error_strategy", "continue")  # "continue" or "stop"
    
    # Get source output from aggregated inputs (already keyed by node name)
    if source_node_name not in aggregated_inputs:
        raise ValueError(
            f"Iterator node {node_id} ({node_name}): source node '{source_node_name}' not found in inputs. "
            f"Available inputs: {list(aggregated_inputs.keys())}"
        )
    
    source_output = aggregated_inputs[source_node_name]
    
    # Extract array using array_key path
    try:
        array_data = _extract_array_from_output(source_output, array_key)
    except ValueError as e:
        raise ValueError(
            f"Iterator node {node_id} ({node_name}): failed to extract array - {e}"
        )
    
    if not isinstance(array_data, list):
        raise ValueError(
            f"Iterator node {node_id} ({node_name}): source '{source_node_name}' does not contain an array. "
            f"Got type: {type(array_data).__name__}, value: {str(array_data)[:100]}"
        )
    
    if len(array_data) == 0:
        logger.warning(f"[run={run_id}] Iterator node {node_id} ({node_name}): empty array, returning empty result")
        return {"output": [], "output_type": "array"}
    
    # Process each item
    results = []
    errors = []
    total_items = len(array_data)
    
    for index, item in enumerate(array_data):
        logger.info(f"[run={run_id}] Iterator node {node_id} ({node_name}): processing item {index + 1}/{total_items}")
        
        # Publish progress (publish_node_status signature: run_id, node_id, status, data=None)
        await publish_node_status(
            run_id,
            node_id,
            "running",
            {
                "iterator_progress": {
                    "current": index + 1,
                    "total": total_items,
                    "percent": int((index + 1) / total_items * 100),
                    "node_name": node_name
                }
            }
        )
        
        # Create item-specific inputs (replace source with current item)
        # Special iterator variables are added for use in prompts/code:
        # - _iterator_item: Current array item
        # - _iterator_index: Zero-based index of current item
        item_inputs = aggregated_inputs.copy()
        item_inputs[source_node_name] = item
        item_inputs["_iterator_item"] = item
        item_inputs["_iterator_index"] = index
        
        # Process item based on node type
        try:
            if node_type_id == "custom-llm":
                result = await _execute_llm_node_iterator(
                    node_id, node_config, item_inputs, item, index, run_id
                )
            elif node_type_id == "custom-python":
                result = await _execute_python_node_iterator(
                    node_id, node_config, item_inputs, item, index, run_id, workflow_id
                )
            else:
                raise ValueError(f"Iterator mode not supported for node type: {node_type_id}")
            
            # Extract output from result
            item_output = result.get("output", result)
            results.append(item_output)
            
        except Exception as e:
            error_info = {
                "index": index,
                "item": str(item)[:100],  # Truncate for logging
                "error": str(e),
                "type": type(e).__name__
            }
            errors.append(error_info)
            logger.error(
                f"[run={run_id}] Iterator node {node_id} ({node_name}): item {index + 1} failed: {e}",
                exc_info=True
            )
            
            # Handle error based on strategy
            if error_strategy == "stop":
                raise Exception(
                    f"Iterator node {node_id} ({node_name}): stopped on item {index + 1} due to error: {e}"
                ) from e
            # else: continue processing (default)
            results.append({"error": str(e), "type": type(e).__name__, "index": index})
    
    logger.info(f"[run={run_id}] Iterator node {node_id} ({node_name}): completed {len(results)} items, {len(errors)} errors")
    
    return {
        "output": results,
        "output_type": "array",
        "errors": errors if errors else None,
        "total_items": total_items,
        "successful_items": len(results) - len(errors)
    }


# ════════════════════════════════════════════════════════════
# Graph-level activity — uses LangGraph
# ════════════════════════════════════════════════════════════

@activity.defn
async def execute_graph_activity(
    workflow_id: str,
    graph_json: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    initial_state: Optional[Dict[str, Any]] = None,
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute the entire graph using **LangGraph** for compilation and
    execution.  Runs OUTSIDE the Temporal sandbox so heavy imports are fine.

    Falls back to a manual topological-sort executor if LangGraph
    compilation fails only when the graph is **acyclic**. If the graph
    has cycles, no fallback is used so the run fails with the real error.

    If initial_state is provided (resume from checkpoint), node_outputs
    are pre-filled and nodes with successful outputs are skipped (unless graph has cycles).

    execution_config: optional per-workflow timeouts (default_node_timeout_seconds, etc.)
    """
    from services.graph.graph_analysis import has_cycle

    activity.heartbeat("Starting graph execution")
    graph_has_cycles = has_cycle(graph_json)
    logger.info(f"[run={run_id}] execute_graph_activity: "
                f"{len(graph_json.get('nodes', []))} nodes, "
                f"{len(graph_json.get('edges', []))} edges"
                f"{', resume mode' if initial_state else ''}"
                f"{', cyclic graph' if graph_has_cycles else ''}")

    try:
        result = await _execute_with_langgraph(
            workflow_id, graph_json, inputs, run_id, initial_state=initial_state, execution_config=execution_config
        )
    except Exception as lg_err:
        if graph_has_cycles:
            logger.warning(
                f"[run={run_id}] LangGraph execution failed on cyclic graph ({lg_err}), "
                f"not using manual topo fallback"
            )
            raise
        logger.warning(
            f"[run={run_id}] LangGraph execution failed ({lg_err}), "
            f"falling back to manual topological sort"
        )
        activity.heartbeat("Falling back to manual execution")
        result = await _execute_manual_topo(
            workflow_id, graph_json, inputs, run_id, initial_state=initial_state, execution_config=execution_config
        )

    # ── Check for suspended wait nodes ──────────────────────────────────────
    if not result.get("error"):
        node_outputs = result.get("node_outputs", {})
        node_map = {str(n["id"]): n for n in graph_json.get("nodes", [])}

        suspended_wait_nodes: Dict[str, str] = {}  # {node_id: channel}
        for nid, output in node_outputs.items():
            if not isinstance(output, dict) or not output.get("__suspended__"):
                continue
            # Only count actual wait nodes (not downstream propagations)
            node_def = node_map.get(nid)
            if node_def and node_def.get("node_type_id") == "wait":
                channel = output.get("channel", "")
                suspended_wait_nodes[nid] = channel

        if suspended_wait_nodes:
            # Build resume_after: for each wait node, find its downstream target(s)
            resume_after: Dict[str, List[str]] = {}
            pending_timeouts: Dict[str, Any] = {}
            edges = graph_json.get("edges", [])
            for wait_node_id in suspended_wait_nodes:
                targets = [
                    str(e["target"])
                    for e in edges
                    if str(e["source"]) == wait_node_id
                ]
                resume_after[wait_node_id] = targets
                # Extract timeout_seconds from the suspended entry
                wait_output = node_outputs.get(wait_node_id, {})
                pending_timeouts[wait_node_id] = wait_output.get("timeout_seconds")

            logger.info(
                f"[run={run_id}] Graph suspended: wait_nodes={list(suspended_wait_nodes.keys())}"
            )
            return {
                "__suspended__": True,
                "pending_waits": suspended_wait_nodes,
                "pending_timeouts": pending_timeouts,
                "resume_after": resume_after,
                "state": result,
            }

    # Persist full state to DB so we don't return it over gRPC (avoids 4MB limit)
    status = "success"
    if result.get("error"):
        status = "cancelled" if result.get("error_type") == "CancelledError" else "error"
    _persist_final_state_to_run(run_id, result, status)
    # Return small payload so Temporal accepts the activity completion
    return {
        "run_id": run_id,
        "status": status,
        "error": (result.get("error") or "")[:500] if result.get("error") else None,
        "workflow_id": workflow_id,
    }


async def _execute_with_langgraph(
    workflow_id: str,
    graph_json: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    initial_state: Optional[Dict[str, Any]] = None,
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compile graph with LangGraph and invoke it. On exception returns partial state."""
    from services.graph.compiler import json_to_langgraph
    import asyncio

    activity.heartbeat("Compiling graph with LangGraph")
    compiled_graph = json_to_langgraph(
        graph_json=graph_json,
        inputs=inputs,
        run_id=run_id,
        temporal_workflow=None,  # we call activities directly from inside this activity
        workflow_id=workflow_id,
        initial_state=initial_state,
        execution_config=execution_config,
    )

    if initial_state and isinstance(initial_state, dict):
        base_state = dict(initial_state)
        base_state.setdefault("inputs", inputs)
        base_state.setdefault("node_outputs", {})
        base_state.setdefault("node_inputs", {})
        base_state.setdefault("node_name_map", {})
        base_state["run_id"] = run_id
        base_state.setdefault("_step_count", 0)
        # Ensure inputs is from initial_state or fallback to inputs
        if "inputs" not in base_state or not base_state["inputs"]:
            base_state["inputs"] = inputs
    else:
        base_state = {
            "inputs": inputs,
            "node_outputs": {},
            "node_inputs": {},
            "node_name_map": {},
            "run_id": run_id,
            "_step_count": 0,
        }

    activity.heartbeat("Invoking LangGraph")
    logger.info(f"[run={run_id}] Invoking compiled LangGraph")

    last_state: Dict[str, Any] = dict(base_state)
    prev_state: Optional[Dict[str, Any]] = None

    async def heartbeat_loop():
        start_time = datetime.now()
        while True:
            await asyncio.sleep(30)
            elapsed = (datetime.now() - start_time).total_seconds()
            activity.heartbeat(f"LangGraph executing... ({int(elapsed)}s elapsed)")

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        # Stream with "values" to get full state after each step; capture for partial on exception
        async for state_chunk in compiled_graph.astream(base_state, stream_mode="values"):
            if isinstance(state_chunk, dict):
                last_state = dict(state_chunk)
                _persist_partial_snapshot_during_execution(
                    run_id, last_state, workflow_id,
                    graph_json=graph_json,
                    prev_state=prev_state,
                )
                prev_state = dict(last_state)
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        activity.heartbeat("LangGraph execution complete")
        logger.info(
            f"[run={run_id}] LangGraph done. "
            f"Outputs: {list(last_state.get('node_outputs', {}).keys())}"
        )
        return last_state
    except asyncio.CancelledError:
        # User clicked Stop: persist partial state to DB (workflow won't receive return),
        # then re-raise so activity is considered cancelled.
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        partial = {
            "inputs": base_state.get("inputs", inputs),
            "node_outputs": last_state.get("node_outputs", base_state.get("node_outputs", {})),
            "node_inputs": last_state.get("node_inputs", base_state.get("node_inputs", {})),
            "node_name_map": last_state.get("node_name_map", base_state.get("node_name_map", {})),
            "error": "Activity cancelled",
            "error_type": "CancelledError",
            "run_id": run_id,
            "workflow_id": workflow_id,
        }
        if last_state.get("_step_count") is not None:
            partial["_step_count"] = last_state["_step_count"]
        logger.warning(
            f"[run={run_id}] Activity cancelled, persisting partial state: "
            f"{len(partial.get('node_outputs', {}))} outputs"
        )
        _persist_partial_state_on_cancel(run_id, partial)
        raise
    except Exception as e:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        # Return partial state so workflow can persist it
        partial = {
            "inputs": base_state.get("inputs", inputs),
            "node_outputs": last_state.get("node_outputs", base_state.get("node_outputs", {})),
            "node_inputs": last_state.get("node_inputs", base_state.get("node_inputs", {})),
            "node_name_map": last_state.get("node_name_map", base_state.get("node_name_map", {})),
            "error": str(e),
            "error_type": type(e).__name__,
            "run_id": run_id,
            "workflow_id": workflow_id,
        }
        if last_state.get("_step_count") is not None:
            partial["_step_count"] = last_state["_step_count"]
        logger.warning(
            f"[run={run_id}] LangGraph failed, returning partial state: "
            f"{len(partial.get('node_outputs', {}))} outputs"
        )
        return partial


async def _execute_manual_topo(
    workflow_id: str,
    graph_json: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    initial_state: Optional[Dict[str, Any]] = None,
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fallback: walk nodes in topological order (Kahn's algorithm)
    and execute them sequentially. Supports resume: if initial_state
    has node_outputs, nodes with successful output are skipped.
    """
    cfg = execution_config or {}
    node_timeout = int(cfg.get("default_node_timeout_seconds", 600))
    nodes = graph_json.get("nodes", [])
    edges = graph_json.get("edges", [])

    # Build lookup structures — ensure all IDs are strings
    node_map: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        nid = str(n["id"])
        node_map[nid] = n

    node_ids = set(node_map.keys())
    in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
    children: Dict[str, list] = {nid: [] for nid in node_ids}

    # ── Validate & build edge structures ──
    skipped_edges = 0
    for edge in edges:
        src = str(edge["source"])
        tgt = str(edge["target"])

        if src not in node_ids or tgt not in node_ids:
            skipped_edges += 1
            logger.warning(
                f"[run={run_id}] Skipping stale edge {src[:8]}→{tgt[:8]}: "
                f"src_exists={src in node_ids}, tgt_exists={tgt in node_ids}"
            )
            continue

        in_degree[tgt] += 1
        children[src].append(tgt)

    if skipped_edges:
        logger.warning(f"[run={run_id}] Skipped {skipped_edges} stale edge(s)")

    queue: deque = deque(nid for nid, deg in in_degree.items() if deg == 0)

    if not queue:
        raise ValueError(
            "No entry nodes found (all nodes have incoming edges, or graph is empty). "
            f"Nodes: {len(node_ids)}, Edges: {len(edges)}"
        )

    # ── Pre-populate the node_name_map for ALL nodes upfront ──
    node_name_map: Dict[str, str] = {}
    for nid, ndata in node_map.items():
        node_name_map[nid] = ndata.get("name", nid)

    # Pre-fill state from initial_state (resume from checkpoint)
    if initial_state and isinstance(initial_state, dict):
        state = {
            "inputs": initial_state.get("inputs") or {str(k): v for k, v in inputs.items()},
            "node_outputs": dict(initial_state.get("node_outputs") or {}),
            "node_inputs": dict(initial_state.get("node_inputs") or {}),
            "node_name_map": dict(initial_state.get("node_name_map") or node_name_map),
            "run_id": run_id,
        }
    else:
        state = {
            "inputs": {str(k): v for k, v in inputs.items()},
            "node_outputs": {},
            "node_inputs": {},
            "node_name_map": node_name_map,
            "run_id": run_id,
        }
    if not state["node_name_map"]:
        state["node_name_map"] = node_name_map

    execution_order = []

    while queue:
        node_id = queue.popleft()
        node_data = node_map[node_id]
        node_type_id = node_data["node_type_id"]
        node_name = state["node_name_map"].get(node_id, node_id)
        node_config = node_data.get("config", {})

        # ── Skip-if-done (resume): already have successful output for this node ──
        existing = state["node_outputs"].get(node_id)
        if existing and isinstance(existing, dict) and "error" not in existing:
            logger.info(f"[run={run_id}] Skipping node {node_id} ({node_name}) — already completed")
            for child_id in children.get(node_id, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
            activity.heartbeat(f"Skipped (done) node {node_id}")
            execution_order.append(node_id)
            continue

        # Build per-node inputs
        if node_type_id == "input":
            node_inputs = {"value": state["inputs"].get(node_id, node_config.get("value", ""))}
        else:
            node_inputs = _aggregate_node_inputs(state, node_id, node_config)
        # Edge node: inject from parent/external input
        if node_config.get("use_input_from_parent"):
            key = node_config.get("external_input_key") or node_name
            if key in state["inputs"]:
                node_inputs["value"] = state["inputs"][key]

        state["node_inputs"][node_id] = node_inputs
        execution_order.append(node_id)

        # ── Check for iterator mode (after input aggregation, before execution) ──
        if _should_use_iterator(node_config):
            # Process with iterator (no workflow in manual mode)
            result = await _process_with_iterator(
                node_id, node_type_id, node_config, node_inputs, run_id, node_name, workflow_id
            )
            
            output = result.get("output", result)
            output_entry = {"output": output}
            if isinstance(result, dict) and result.get("logs"):
                output_entry["logs"] = result["logs"]
            if isinstance(result, dict) and result.get("error"):
                output_entry["error"] = result["error"]
            if isinstance(result, dict) and result.get("errors"):
                output_entry["errors"] = result["errors"]
            state["node_outputs"][node_id] = output_entry
            state["node_outputs"][node_name] = output_entry
            logger.info(f"[run={run_id}] Node {node_id} ({node_name}) completed successfully")
            
            # Release downstream nodes
            for child_id in children.get(node_id, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
            activity.heartbeat(f"Completed node {node_id}")
            _persist_partial_snapshot_during_execution(run_id, state, workflow_id)
            continue  # Skip normal execution

        # ── Workflow node: run sub-workflow ──
        if node_type_id == "workflow_node":
            ref_workflow_id = node_config.get("workflow_id")
            if not ref_workflow_id:
                raise ValueError("workflow_node missing config.workflow_id")
            merged_inputs = _merge_upstream_outputs_for_workflow_node(state, node_id, graph_json)
            await publish_node_status(run_id, node_id, "running")
            try:
                result = await _run_subworkflow(ref_workflow_id, merged_inputs, run_id)
                output_dict = result.get("output", {})
                child_run_id = result.get("child_run_id")
                child_workflow_id = result.get("child_workflow_id") or ref_workflow_id
                output_entry = {"output": output_dict}
                if child_run_id is not None:
                    output_entry["child_run_id"] = child_run_id
                    output_entry["child_workflow_id"] = child_workflow_id
                state["node_outputs"][node_id] = output_entry
                state["node_outputs"][node_name] = output_entry
                await publish_node_status(run_id, node_id, "success", {"output": output_dict})
            except Exception as exc:
                import traceback as tb
                logger.error(f"[run={run_id}] workflow_node {node_id} ({node_name}) failed: {exc}", exc_info=True)
                error_output = {
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "traceback": tb.format_exc(),
                    "node_id": node_id,
                    "node_name": node_name,
                    "node_type": node_type_id,
                }
                state["node_outputs"][node_id] = error_output
                state["node_outputs"][node_name] = error_output
                await publish_node_status(run_id, node_id, "error", {"error": {"type": type(exc).__name__, "message": str(exc)}})
            for child_id in children.get(node_id, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
            activity.heartbeat(f"Completed workflow_node {node_id}")
            _persist_partial_snapshot_during_execution(run_id, state, workflow_id)
            continue

        # Execute
        try:
            logger.info(f"[run={run_id}] Executing node {node_id} ({node_name}) [{node_type_id}]")
            if node_type_id == "input":
                result = await execute_input_node_activity(node_id, node_config, node_inputs, run_id)
            elif node_type_id in ("custom-python", "condition-python"):
                result = await execute_python_node_activity(
                    node_id, node_config, node_inputs, run_id, workflow_id, timeout_seconds=node_timeout
                )
            elif node_type_id == "custom-llm":
                result = await execute_llm_node_activity(node_id, node_config, node_inputs, run_id)
            elif node_type_id == "memory":
                result = await execute_memory_node_activity(node_id, node_config, node_inputs, run_id)
            elif node_type_id == "html-viewer":
                result = await execute_html_viewer_node_activity(node_id, node_config, node_inputs, run_id)
            else:
                raise ValueError(f"Unknown node type: {node_type_id}")

            output = result.get("output", result)
            # Include logs in the stored output if available
            output_entry = {"output": output}
            if isinstance(result, dict) and result.get("logs"):
                output_entry["logs"] = result["logs"]
            if isinstance(result, dict) and result.get("error"):
                output_entry["error"] = result["error"]
            state["node_outputs"][node_id] = output_entry
            # Also store by name for easier access in user code
            state["node_outputs"][node_name] = output_entry
            logger.info(f"[run={run_id}] Node {node_id} ({node_name}) completed successfully")

        except Exception as exc:
            import traceback as tb
            logger.error(f"[run={run_id}] Node {node_id} ({node_name}) failed: {exc}", exc_info=True)
            error_output = {
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": tb.format_exc(),
                "node_id": node_id,
                "node_name": node_name,
                "node_type": node_type_id,
            }
            state["node_outputs"][node_id] = error_output
            state["node_outputs"][node_name] = error_output
            activity.heartbeat(f"Node {node_id} failed: {exc}")

        # Release downstream — safe: children only contains validated targets
        for child_id in children.get(node_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

        activity.heartbeat(f"Completed node {node_id}")
        _persist_partial_snapshot_during_execution(run_id, state, workflow_id)

    state["execution_order"] = execution_order
    # Set top-level error if any node failed (so workflow can save as error/partial)
    for out in state.get("node_outputs", {}).values():
        if isinstance(out, dict) and "error" in out:
            state["error"] = "One or more nodes failed"
            break
    return state


# ════════════════════════════════════════════════════════════
# Per-node-type activities
# ════════════════════════════════════════════════════════════

@activity.defn
async def execute_input_node_activity(
    node_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """Execute input node — returns the user-supplied (or default) value."""
    await publish_node_status(run_id, node_id, "running")
    try:
        value = inputs.get("value", node_config.get("value", ""))
        result = {"output": value, "output_type": "text"}
        await publish_node_status(run_id, node_id, "success", result)
        logger.info(f"[run={run_id}] Input node {node_id}: value='{str(value)[:80]}'")
        return result
    except Exception as e:
        await publish_node_status(run_id, node_id, "error", {"error": {"type": type(e).__name__, "message": str(e)}})
        raise


@activity.defn
async def execute_html_viewer_node_activity(
    node_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """HTML viewer (issue17): scan all upstream string values, pick the one that
    looks most like HTML, strip code fences. The frontend renders the cleaned
    output inside a sandboxed iframe.

    `_aggregate_node_inputs` aggregates every completed node's output into the
    activity's `inputs` dict — not just edge-connected upstream — so the activity
    sees an entry node's plain string alongside an LLM's HTML report. A
    score-based pick (HTML markers > plain text) matches user intent without
    any wiring discipline or graph plumbing.
    """
    import re
    TAG_PAT = re.compile(
        r'<(?:div|p|span|h[1-6]|ul|ol|table|li|a|img|section|article)\b',
        re.IGNORECASE,
    )
    FENCE_PAT = re.compile(
        r'^```(?:html)?\s*\n?([\s\S]*?)\n?```\s*$',
        re.IGNORECASE,
    )

    def _score_html(s: str) -> float:
        sc = 0.0
        if FENCE_PAT.match(s.strip()) and '<' in s:
            sc += 100
        low = s.lower()
        if '<!doctype' in low:
            sc += 50
        if '<html' in low or '<body' in low:
            sc += 50
        sc += min(50, 5 * len(TAG_PAT.findall(s)))
        sc += 0.001 * len(s)  # length tiebreak
        return sc

    await publish_node_status(run_id, node_id, "running")
    try:
        candidates: list = []
        for v in (inputs or {}).values():
            if isinstance(v, str) and v.strip():
                candidates.append((_score_html(v), v))
            elif isinstance(v, dict) and isinstance(v.get("output"), str) and v["output"].strip():
                inner = v["output"]
                candidates.append((_score_html(inner), inner))

        html = ""
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            top_score, top_html = candidates[0]
            # If nothing scored on HTML markers (only the length tiebreak),
            # fall back to longest string — still beats picking by completion order.
            if top_score <= 0.05:
                top_html = max((c[1] for c in candidates), key=len)
            # Strip code fence backend-side so node_outputs[id].output is clean HTML.
            m = FENCE_PAT.match(top_html.strip())
            html = (m.group(1) if m else top_html).strip()

        result = {"output": html, "output_type": "html"}
        await publish_node_status(run_id, node_id, "success", result)
        logger.info(
            f"[run={run_id}] HTML viewer {node_id}: picked {len(html)} chars "
            f"from {len(candidates)} candidates"
        )
        return result
    except Exception as e:
        await publish_node_status(
            run_id, node_id, "error",
            {"error": {"type": type(e).__name__, "message": str(e)}},
        )
        raise


@activity.defn
async def execute_python_node_activity(
    node_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    workflow_id: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute Python node in a Docker container with storage access and environment variables.
    timeout_seconds: max run time for the container; if None, loaded from workflow execution_config or default 600.
    """
    await publish_node_status(run_id, node_id, "running")

    if timeout_seconds is None and workflow_id:
        from database.connection import SessionLocal
        from database.models import Workflow
        from uuid import UUID
        db = SessionLocal()
        try:
            w = db.query(Workflow).filter(
                Workflow.id == UUID(workflow_id),
                Workflow.deleted_at.is_(None),
            ).first()
            if w and w.execution_config:
                timeout_seconds = int((w.execution_config or {}).get("default_node_timeout_seconds", 600))
            else:
                timeout_seconds = 600
        finally:
            db.close()
    if timeout_seconds is None:
        timeout_seconds = 600

    # Define heartbeat callback that sends Temporal heartbeats
    def send_heartbeat(message: str):
        try:
            activity.heartbeat(f"Node {node_id}: {message}")
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")
    
    try:
        from services.docker.executor import DockerExecutor
        from services.storage.manager import StorageManager
        from database.connection import SessionLocal
        from database.models import Workflow, WorkflowNode, StorageConfig
        from utils.storage_helpers import storage_config_to_env_vars

        executor = DockerExecutor()
        code = node_config.get("code", "")
        requirements = node_config.get("requirements", "")

        # Fetch storage configs from database for this node
        # Storage configs are stored in settings (StorageConfig table)
        db = SessionLocal()
        try:
            storage_configs = StorageManager.get_node_storage_configs(node_config, db)
            # Returns: {"alias": {"storage_type": "...", "config": {...}}}
            
            # ── Environment Variable Injection ──
            merged_env = {}
            
            # 1. Get workflow-level config
            if workflow_id:
                workflow = db.query(Workflow).filter_by(id=workflow_id).first()
                if workflow and workflow.workflow_config:
                    merged_env.update(workflow.workflow_config)
            
            # 2. Get node-level config (overrides workflow config)
            node = db.query(WorkflowNode).filter_by(id=node_id).first()
            if node and node.node_config:
                merged_env.update(node.node_config)
            
            # 3. Resolve storage configs to env vars
            for alias, storage_info in storage_configs.items():
                storage_id = storage_info.get("storage_id")
                if storage_id:
                    storage = db.query(StorageConfig).filter_by(
                        id=storage_id,
                        deleted_at=None
                    ).first()
                    if storage:
                        storage_env = storage_config_to_env_vars(storage)
                        merged_env.update(storage_env)
            
            # 4. Add system env vars
            merged_env.update({
                "WORKFLOW_ID": str(workflow_id) if workflow_id else "",
                "NODE_ID": str(node_id),
                "RUN_ID": str(run_id),
            })
            
            logger.debug(f"[run={run_id}] Node {node_id}: Injected {len(merged_env)} environment variables")
        finally:
            db.close()

        # Generate requirements based on linked storages
        # Add storage dependencies dynamically per node
        storage_dependencies = {
            "postgresql": "psycopg2-binary>=2.9.0",
            "redis": "redis>=5.0.0",
            "mongodb": "pymongo>=4.6.0",
            "chroma": "chromadb>=0.4.0",
            "minio": "boto3>=1.28.0",
            "s3": "boto3>=1.28.0",
            "local_file": None  # No extra dependency
        }

        # Get unique storage types for this node
        storage_types = {info["storage_type"] for info in storage_configs.values()}

        # Add storage dependencies to node requirements
        additional_requirements = []
        for storage_type in storage_types:
            dep = storage_dependencies.get(storage_type)
            if dep:
                additional_requirements.append(dep)

        # Merge with existing requirements
        if requirements:
            requirements = requirements + "\n" + "\n".join(additional_requirements)
        else:
            requirements = "\n".join(additional_requirements)

        logger.info(
            f"[run={run_id}] Python node {node_id}: "
            f"code_len={len(code)}, storages={list(storage_configs.keys())}, "
            f"storage_types={storage_types}, additional_deps={additional_requirements}"
        )

        if not code.strip():
            raise ValueError("Python node has no code to execute")

        # Mark current node in Redis so partial snapshot can include its logs (Fix 6)
        await _set_redis_current_node(run_id, node_id)

        # Stream logs to Redis in real-time
        log_buffer = []  # Buffer to accumulate logs
        log_lock = asyncio.Lock()  # Lock for thread-safe log accumulation
        
        async def publish_logs(new_logs: str):
            """Publish logs to Redis for real-time viewing and persist for partial snapshot (Fix 6)."""
            try:
                async with log_lock:
                    # Accumulate logs in buffer
                    log_buffer.append(new_logs)
                    # Publish accumulated logs
                    accumulated_logs = "\n".join(log_buffer)

                await publish_node_status(
                    run_id,
                    node_id,
                    "running",
                    {"logs": accumulated_logs, "status": "executing"}
                )
                # Persist running node logs so partial snapshot / cancel can include them
                await _set_redis_node_logs(run_id, node_id, accumulated_logs)
            except Exception as e:
                logger.warning(f"Failed to publish logs: {e}")

        # Create a synchronous wrapper for the async log callback
        # Since we're already in an async context, we can schedule the coroutine
        def log_callback_sync(new_logs: str):
            """Synchronous wrapper for async log publishing"""
            try:
                # We're in an async context (inside execute_python_node_activity),
                # so we can safely create a task
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule it as a task (fire and forget)
                    loop.create_task(publish_logs(new_logs))
                except RuntimeError:
                    # No running loop - shouldn't happen but handle gracefully
                    logger.warning("No running event loop for log callback, logs will be published at end")
            except Exception as e:
                logger.warning(f"Failed to schedule log publishing: {e}")

        # Execute with heartbeat callback and longer timeout for Playwright/Drive operations
        result = await executor.execute_python_node(
            code=code,
            requirements=requirements,
            inputs=inputs,
            storage_configs=storage_configs,
            environment_variables=merged_env,  # Pass merged environment variables
            timeout=timeout_seconds,
            heartbeat_callback=send_heartbeat,  # Pass heartbeat callback
            log_callback=log_callback_sync,  # Pass log callback for real-time streaming
        )

        await _clear_redis_current_node(run_id)
        
        # Publish final logs if available
        if result.get("logs"):
            await publish_logs(result["logs"])

        # If the executor returned an error field, treat it as failure
        if result.get("error"):
            error_msg = result["error"]
            logs = result.get("logs", "")
            logger.warning(f"[run={run_id}] Python node {node_id} error: {error_msg[:200]}")
            await publish_node_status(
                run_id, 
                node_id, 
                "error", 
                {
                    "error": {"type": "ExecutionError", "message": error_msg[:500]},
                    "logs": logs[-5000:] if logs else ""  # Last 5KB of logs
                }
            )
            return result

        await publish_node_status(run_id, node_id, "success", result)
        logger.info(f"[run={run_id}] Python node {node_id} completed")
        return result

    except asyncio.CancelledError:
        # Publish accumulated logs before re-raising so UI and partial state get them (Fix 2)
        accumulated_logs = "\n".join(log_buffer) if log_buffer else "No logs captured"
        try:
            extra = getattr(executor, "_last_cancelled_logs", None)
            if extra:
                accumulated_logs = (accumulated_logs + "\n" + extra) if accumulated_logs else extra
        except NameError:
            pass
        except Exception:
            pass
        logger.warning(
            f"[run={run_id}] Python node {node_id} cancelled. "
            f"Accumulated {len(log_buffer)} log chunks, publishing before re-raise"
        )
        try:
            await publish_node_status(run_id, node_id, "cancelled", {
                "logs": accumulated_logs[-5000:] if len(accumulated_logs) > 5000 else accumulated_logs,
                "status": "cancelled",
            })
            await _set_redis_cancelled_logs(run_id, node_id, accumulated_logs)
            await _clear_redis_current_node(run_id)
        except Exception as e:
            logger.warning(f"Failed to publish cancelled logs: {e}")
        raise

    except Exception as e:
        logger.error(f"[run={run_id}] Python node {node_id} exception: {e}", exc_info=True)
        import traceback
        try:
            await _clear_redis_current_node(run_id)
        except Exception:
            pass
        error_detail = {
            "type": type(e).__name__, 
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        await publish_node_status(run_id, node_id, "error", {"error": error_detail})
        raise


@activity.defn
async def execute_llm_node_activity(
    node_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """Execute LLM node via the LLMExecutor."""
    await publish_node_status(run_id, node_id, "running")
    try:
        from services.llm.executor import LLMExecutor

        executor = LLMExecutor()
        prompt_template = node_config.get("prompt", "")
        config_id = node_config.get("configId") or None  # Treat empty string as None

        # DEBUG: Log inputs structure for troubleshooting
        logger.info(
            f"[run={run_id}] LLM node {node_id}: config_id={config_id}, "
            f"prompt_len={len(prompt_template)}, input_keys={list(inputs.keys())}"
        )
        logger.debug(
            f"[run={run_id}] LLM node {node_id} inputs detail: "
            f"input_types={[(k, type(v).__name__) for k, v in inputs.items()]}"
        )
        for key, value in inputs.items():
            if isinstance(value, dict):
                logger.debug(
                    f"[run={run_id}]   {key}: dict with keys {list(value.keys())}"
                )
                if "output" in value:
                    output_val = value["output"]
                    logger.debug(
                        f"[run={run_id}]     output value type: {type(output_val).__name__}, "
                        f"preview: {str(output_val)[:100]}"
                    )
            else:
                logger.debug(
                    f"[run={run_id}]   {key}: {type(value).__name__} = {str(value)[:100]}"
                )

        if not prompt_template.strip() and not inputs:
            raise ValueError("LLM node has no prompt and no inputs")

        activity.heartbeat(f"LLM node {node_id}: calling LLM API")
        result = await executor.execute_llm_node(
            prompt_template=prompt_template,
            inputs=inputs,
            config_id=config_id,
            run_id=run_id,
        )

        await publish_node_status(run_id, node_id, "success", result)
        logger.info(f"[run={run_id}] LLM node {node_id} completed, tokens={result.get('tokens_used')}")
        return result

    except Exception as e:
        logger.error(f"[run={run_id}] LLM node {node_id} exception: {e}", exc_info=True)
        await publish_node_status(run_id, node_id, "error", {"error": {"type": type(e).__name__, "message": str(e)}})
        raise


@activity.defn
async def execute_memory_node_activity(
    node_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    """Execute memory node — store/retrieve from memory."""
    await publish_node_status(run_id, node_id, "running")
    try:
        # TODO: Implement memory node execution (context storage / RAG retrieval)
        result = {
            "output": "Memory node execution not yet implemented — passing inputs through",
            "output_type": "text",
        }
        # Pass-through: forward upstream data
        if inputs:
            first_val = next(iter(inputs.values()), None)
            if first_val:
                result["output"] = first_val

        await publish_node_status(run_id, node_id, "success", result)
        logger.info(f"[run={run_id}] Memory node {node_id} completed (pass-through)")
        return result
    except Exception as e:
        await publish_node_status(run_id, node_id, "error", {"error": {"type": type(e).__name__, "message": str(e)}})
        raise


# ════════════════════════════════════════════════════════════
# Iterator node execution functions
# ════════════════════════════════════════════════════════════

async def _execute_llm_node_iterator(
    node_id: str,
    node_config: Dict[str, Any],
    item_inputs: Dict[str, Any],
    item: Any,
    index: int,
    run_id: str,
) -> Dict[str, Any]:
    """
    Execute LLM node for a single iterator item.
    
    Args:
        node_id: Node ID
        node_config: Node configuration (with iterator config removed for LLM execution)
        item_inputs: Inputs with source replaced by current item (already aggregated, keyed by node names)
        item: Current array item being processed
        index: Current item index
        run_id: Run ID
    
    Returns:
        LLM execution result for this item
    """
    from services.llm.executor import LLMExecutor
    
    # Create clean config without iterator settings
    llm_config = node_config.copy()
    llm_config.pop("iterator", None)
    
    executor = LLMExecutor()
    prompt_template = llm_config.get("prompt", "")
    config_id = llm_config.get("configId") or None
    
    # Format prompt with item-specific inputs
    # The item is available as the source_node_name in item_inputs
    result = await executor.execute_llm_node(
        prompt_template=prompt_template,
        inputs=item_inputs,
        config_id=config_id,
        run_id=run_id,
    )
    
    return result


async def _execute_python_node_iterator(
    node_id: str,
    node_config: Dict[str, Any],
    item_inputs: Dict[str, Any],
    item: Any,
    index: int,
    run_id: str,
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute Python node for a single iterator item.
    
    IMPORTANT: Must fetch storage_configs (same as execute_python_node_activity does at lines 456-463).
    
    Args:
        node_id: Node ID
        node_config: Node configuration (with iterator config removed for Python execution)
        item_inputs: Inputs with source replaced by current item (already aggregated, keyed by node names)
        item: Current array item being processed
        index: Current item index
        run_id: Run ID
    
    Returns:
        Python execution result for this item
    """
    from services.docker.executor import DockerExecutor
    from services.storage.manager import StorageManager
    from database.connection import SessionLocal
    
    # Create clean config without iterator settings
    python_config = node_config.copy()
    python_config.pop("iterator", None)
    
    executor = DockerExecutor()
    code = python_config.get("code", "")
    requirements = python_config.get("requirements", "")
    
    if not code.strip():
        raise ValueError("Python node has no code to execute")
    
    # Fetch storage configs from database for this node (REQUIRED - same as execute_python_node_activity)
    db = SessionLocal()
    try:
        storage_configs = StorageManager.get_node_storage_configs(python_config, db)
        # Returns: {"alias": {"storage_type": "...", "config": {...}}}
        
        # ── Environment Variable Injection (same as execute_python_node_activity) ──
        merged_env = {}
        
        # 1. Get workflow-level config
        if workflow_id:
            from database.models import Workflow
            workflow = db.query(Workflow).filter_by(id=workflow_id).first()
            if workflow and workflow.workflow_config:
                merged_env.update(workflow.workflow_config)
        
        # 2. Get node-level config (overrides workflow config)
        from database.models import WorkflowNode
        from utils.storage_helpers import storage_config_to_env_vars
        from database.models import StorageConfig
        
        node = db.query(WorkflowNode).filter_by(id=node_id).first()
        if node and node.node_config:
            merged_env.update(node.node_config)
        
        # 3. Resolve storage configs to env vars
        for alias, storage_info in storage_configs.items():
            storage_id = storage_info.get("storage_id")
            if storage_id:
                storage = db.query(StorageConfig).filter_by(
                    id=storage_id,
                    deleted_at=None
                ).first()
                if storage:
                    storage_env = storage_config_to_env_vars(storage)
                    merged_env.update(storage_env)
        
        # 4. Add system env vars
        merged_env.update({
            "WORKFLOW_ID": str(workflow_id) if workflow_id else "",
            "NODE_ID": str(node_id),
            "RUN_ID": str(run_id),
        })
    finally:
        db.close()
    
    # Generate requirements based on linked storages (same as execute_python_node_activity)
    storage_dependencies = {
        "postgresql": "psycopg2-binary>=2.9.0",
        "redis": "redis>=5.0.0",
        "mongodb": "pymongo>=4.6.0",
        "chroma": "chromadb>=0.4.0",
        "minio": "boto3>=1.28.0",
        "s3": "boto3>=1.28.0",
        "local_file": None
    }
    
    storage_types = {info["storage_type"] for info in storage_configs.values()}
    additional_requirements = []
    for storage_type in storage_types:
        dep = storage_dependencies.get(storage_type)
        if dep:
            additional_requirements.append(dep)
    
    if requirements:
        requirements = requirements + "\n" + "\n".join(additional_requirements)
    else:
        requirements = "\n".join(additional_requirements)
    
    # Execute with storage configs and environment variables
    result = await executor.execute_python_node(
        code=code,
        requirements=requirements,
        inputs=item_inputs,
        storage_configs=storage_configs,  # REQUIRED: Must pass storage_configs
        environment_variables=merged_env,  # Pass merged environment variables
        timeout=60,
    )
    
    return result


@activity.defn
async def _process_with_iterator_activity(
    node_id: str,
    node_type_id: str,
    node_config: Dict[str, Any],
    inputs: Dict[str, Any],
    run_id: str,
    node_name: str,
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Temporal activity wrapper for iterator processing.
    
    Note: This activity is defined in the same file as other activities,
    so no additional registration is needed. It will be automatically
    available to the Temporal worker.
    """
    return await _process_with_iterator(
        node_id, node_type_id, node_config, inputs, run_id, node_name, workflow_id
    )


# ════════════════════════════════════════════════════════════
# Persistence & status publishing activities
# ════════════════════════════════════════════════════════════


def _persist_partial_state_on_cancel(run_id: str, partial: Dict[str, Any]) -> None:
    """
    Write partial state directly to DB when activity is cancelled.
    The workflow will not receive the activity return, so we persist here
    and the workflow's except block will skip overwriting (see save_run_results_activity).
    Merge any run_cancelled_logs from Redis (Fix 6) so cancelled node logs are in snapshot.
    """
    from datetime import datetime, timezone
    from database.connection import SessionLocal
    from database.models import RunHistory
    import json
    import redis
    from config.settings import get_settings

    # Merge cancelled node logs from Redis (set by execute_python_node_activity on CancelledError)
    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        cancelled_raw = r.get(f"run_cancelled_logs:{run_id}")
        if cancelled_raw:
            cancelled = json.loads(cancelled_raw)
            node_outputs = partial.setdefault("node_outputs", {})
            for nid, logs in cancelled.items():
                node_outputs[nid] = {"output": None, "logs": logs, "error": "Activity cancelled"}
            r.delete(f"run_cancelled_logs:{run_id}")
        r.close()
    except Exception as e:
        logger.warning(f"[run={run_id}] Failed to merge run_cancelled_logs: {e}")

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            logger.error(f"[run={run_id}] Run not found, cannot persist partial state on cancel")
            return
        run.snapshot = _sanitize_for_jsonb(partial)
        run.status = "cancelled"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run.completed_at = now
        if run.started_at is not None:
            run.duration = (now - run.started_at).total_seconds()
        run.error_message = partial.get("error", "Activity cancelled")
        db.commit()
        logger.info(f"[run={run_id}] Persisted partial state on cancel: {len(partial.get('node_outputs', {}))} outputs")
    except Exception as e:
        logger.exception(f"[run={run_id}] Failed to persist partial state on cancel: {e}")
        db.rollback()
    finally:
        db.close()


def _persist_final_state_to_run(run_id: str, final_state: Dict[str, Any], status: str) -> None:
    """
    Write full final state to run_history so we don't need to return it over gRPC.
    Used by execute_graph_activity before returning a small payload (avoids 4MB limit).
    """
    from datetime import datetime, timezone
    from database.connection import SessionLocal
    from database.models import RunHistory

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            logger.error(f"[run={run_id}] Run not found, cannot persist final state")
            return
        run.snapshot = _sanitize_for_jsonb(final_state)
        run.status = status
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run.completed_at = now
        if run.started_at is not None:
            run.duration = (now - run.started_at).total_seconds()
        err_msg = final_state.get("error")
        run.error_message = (err_msg[:5000] if err_msg and len(err_msg) > 5000 else err_msg) if err_msg else None
        node_outputs = final_state.get("node_outputs") or {}
        node_name_map = final_state.get("node_name_map") or {}
        name_values = set(node_name_map.values()) if node_name_map else set()
        unique_outputs = {
            k: v for k, v in node_outputs.items()
            if k not in name_values
        }
        run.total_nodes = len(unique_outputs)
        run.completed_nodes = sum(
            1 for v in unique_outputs.values()
            if not (isinstance(v, dict) and "error" in v)
        )
        run.failed_nodes = sum(
            1 for v in unique_outputs.values()
            if isinstance(v, dict) and "error" in v
        )
        db.commit()
        logger.info(f"[run={run_id}] Persisted final state: status={status}, outputs={len(unique_outputs)}")
    except Exception as e:
        logger.exception(f"[run={run_id}] Failed to persist final state: {e}")
        db.rollback()
    finally:
        db.close()


def _persist_partial_snapshot_during_execution(
    run_id: str,
    state: Dict[str, Any],
    workflow_id: str = None,
    graph_json: Dict[str, Any] = None,
    prev_state: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write current state to the run's snapshot in DB while execution is still running.
    Only updates if run.status is still 'running'. Does not change status or completed_at.
    Allows the frontend to restore node statuses after refresh (seed from snapshot).
    For loop support (Phase 2): also persist _step_count, last_executed_node_id, next_node_id
    so resume can start from the first non-saved node.
    """
    from database.connection import SessionLocal
    from database.models import RunHistory

    snapshot = {
        "inputs": state.get("inputs", {}),
        "node_outputs": dict(state.get("node_outputs", {})),
        "node_inputs": dict(state.get("node_inputs", {})),
        "node_name_map": dict(state.get("node_name_map", {})),
        # Per-call history for looping nodes (issue9). Keyed by node_id.
        "node_iteration_outputs": dict(state.get("node_iteration_outputs", {})),
        "run_id": run_id,
    }
    if state.get("_step_count") is not None:
        snapshot["_step_count"] = state["_step_count"]
    if workflow_id:
        snapshot["workflow_id"] = workflow_id

    # Resolve last-executed node and next node(s) for resume
    if graph_json and prev_state is not None:
        node_map = {str(n["id"]): n for n in graph_json.get("nodes", [])}
        node_outputs_now = state.get("node_outputs") or {}
        node_outputs_prev = prev_state.get("node_outputs") or {}
        last_executed = None
        for nid in node_map:
            if node_outputs_now.get(nid) != node_outputs_prev.get(nid):
                last_executed = nid
                break
        if last_executed and graph_json.get("edges") is not None:
            from services.graph.graph_analysis import get_next_node_ids, has_cycle
            edge_map = {}
            for e in graph_json["edges"]:
                src = str(e.get("source"))
                tgt = str(e.get("target"))
                if src in node_map and tgt in node_map:
                    edge_map.setdefault(src, []).append({
                        "target": tgt,
                        "weight": e.get("weight", 1.0),
                        **({"source_handle": e["source_handle"]} if e.get("source_handle") in ("true", "false") else {}),
                    })
            next_ids = get_next_node_ids(graph_json, edge_map, node_map, last_executed, state)
            snapshot["last_executed_node_id"] = last_executed
            if next_ids:
                snapshot["next_node_id"] = next_ids[0]
            if has_cycle(graph_json):
                snapshot["_has_cycles"] = True

    # Merge running node logs from Redis (Fix 6) so snapshot includes current node's logs
    try:
        import redis
        from config.settings import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        current_node_id = r.get(f"run_current_node:{run_id}")
        if current_node_id:
            logs = r.get(f"run_logs:{run_id}:{current_node_id}")
            if logs:
                node_outputs = snapshot.setdefault("node_outputs", {})
                existing = node_outputs.get(current_node_id) or {}
                existing = dict(existing)
                existing["logs"] = logs
                existing["status"] = "running"
                node_outputs[current_node_id] = existing
        r.close()
    except Exception as e:
        logger.warning(f"[run={run_id}] Failed to merge run_logs into partial snapshot: {e}")

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            return
        if run.status != "running":
            return
        run.snapshot = _sanitize_for_jsonb(snapshot)
        db.commit()
    except Exception as e:
        logger.warning(f"[run={run_id}] Failed to persist partial snapshot during execution: {e}")
        db.rollback()
    finally:
        db.close()


@activity.defn
async def save_run_results_activity(
    run_id: str,
    final_state: Dict[str, Any],
    status: str,
) -> None:
    """Save run results (snapshot, duration, statistics) to database.
    When execute_graph_activity already persisted (small payload), only ensure stats/status.
    """
    from database.connection import SessionLocal
    from database.models import RunHistory
    from sqlalchemy.sql import func

    logger.info(f"[run={run_id}] Saving results: status={status}")

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")

        incoming_outputs = final_state.get("node_outputs") or {}
        existing_snapshot = (run.snapshot or {}) if isinstance(run.snapshot, dict) else {}
        existing_outputs = existing_snapshot.get("node_outputs") or {}

        # Already persisted by execute_graph_activity (small payload return)
        already_persisted = (
            run.completed_at is not None
            and existing_outputs
            and not incoming_outputs
            and "run_id" in final_state
        )
        if already_persisted:
            run.status = status
            if run.started_at is not None and run.completed_at is not None:
                run.duration = (run.completed_at - run.started_at).total_seconds()
            node_outputs = existing_outputs
            node_name_map = existing_snapshot.get("node_name_map") or {}
            name_values = set(node_name_map.values()) if node_name_map else set()
            unique_outputs = {k: v for k, v in node_outputs.items() if k not in name_values}
            run.total_nodes = len(unique_outputs)
            run.completed_nodes = sum(
                1 for v in unique_outputs.values()
                if not (isinstance(v, dict) and "error" in v)
            )
            run.failed_nodes = sum(
                1 for v in unique_outputs.values()
                if isinstance(v, dict) and "error" in v
            )
            if final_state.get("error") and not run.error_message:
                run.error_message = (final_state.get("error") or "")[:5000]
            db.commit()
            logger.info(f"[run={run_id}] Results already persisted by graph activity, synced stats")
            return

        # Preserve partial snapshot when workflow passed empty payload after cancel
        preserve_partial = (
            status == "error"
            and not incoming_outputs
            and existing_outputs
        )
        if preserve_partial:
            run.status = "cancelled"
            run.completed_at = datetime.utcnow()  # Python datetime so the subtraction below works without commit+refresh
            run.error_message = final_state.get("error", "Activity cancelled")
            if run.started_at is not None:
                run.duration = (run.completed_at - run.started_at).total_seconds()
            # Keep existing snapshot; compute stats from it
            node_outputs = existing_outputs
            node_name_map = existing_snapshot.get("node_name_map") or {}
            logger.info(f"[run={run_id}] Preserving partial snapshot (activity wrote on cancel)")
        else:
            run.status = status
            run.completed_at = func.now()
            run.snapshot = _sanitize_for_jsonb(final_state)
            db.commit()
            db.refresh(run)
            if run.started_at is not None and run.completed_at is not None:
                run.duration = (run.completed_at - run.started_at).total_seconds()
            node_outputs = final_state.get("node_outputs", {})
            node_name_map = final_state.get("node_name_map", {})

        # Node statistics — only count UUID-keyed entries to avoid
        # double-counting (outputs are stored by both node_id and node_name)
        name_values = set(node_name_map.values()) if node_name_map else set()
        unique_outputs = {
            k: v for k, v in node_outputs.items()
            if k not in name_values
        }
        run.total_nodes = len(unique_outputs)
        run.completed_nodes = sum(
            1 for v in unique_outputs.values()
            if not (isinstance(v, dict) and "error" in v)
        )
        run.failed_nodes = sum(
            1 for v in unique_outputs.values()
            if isinstance(v, dict) and "error" in v
        )

        db.commit()
        logger.info(f"[run={run_id}] Results saved: total={run.total_nodes}, "
                     f"ok={run.completed_nodes}, failed={run.failed_nodes}")
    finally:
        db.close()


@activity.defn
async def publish_workflow_status_activity(
    run_id: str,
    status: str,
    data: Dict[str, Any] = None,
) -> None:
    """Publish workflow-level status update to Redis."""
    await publish_node_status(run_id, "__workflow__", status, data or {})


# ════════════════════════════════════════════════════════════
# Redis pub/sub helper
# ════════════════════════════════════════════════════════════

async def publish_node_status(
    run_id: str,
    node_id: str,
    status: str,
    data: Dict[str, Any] = None,
) -> None:
    """
    Publish a node status event to Redis Pub/Sub.

    The frontend WebSocket handler subscribes to ``run_updates:{run_id}``
    and relays these messages to the browser.
    """
    import json
    import redis.asyncio as redis
    from config.settings import get_settings

    try:
        settings = get_settings()
        redis_client = await redis.from_url(settings.redis_url, decode_responses=False)

        message = {
            "type": "NODE_STATUS" if node_id != "__workflow__" else "WORKFLOW_STATUS",
            "run_id": run_id,
            "node_id": node_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        }

        await redis_client.publish(f"run_updates:{run_id}", json.dumps(message))
        await redis_client.close()
    except Exception as e:
        logger.warning(f"Failed to publish node status: {e}")


async def _set_redis_current_node(run_id: str, node_id: str) -> None:
    """Set which node is currently running (for persisting its logs in partial snapshot)."""
    import redis.asyncio as redis
    from config.settings import get_settings
    try:
        settings = get_settings()
        client = await redis.from_url(settings.redis_url, decode_responses=True)
        await client.set(f"run_current_node:{run_id}", node_id, ex=86400)
        await client.close()
    except Exception as e:
        logger.warning(f"Failed to set run_current_node: {e}")


async def _clear_redis_current_node(run_id: str) -> None:
    """Clear current node key when node completes or is cancelled."""
    import redis.asyncio as redis
    from config.settings import get_settings
    try:
        settings = get_settings()
        client = await redis.from_url(settings.redis_url, decode_responses=True)
        await client.delete(f"run_current_node:{run_id}")
        await client.close()
    except Exception as e:
        logger.warning(f"Failed to clear run_current_node: {e}")


async def _set_redis_node_logs(run_id: str, node_id: str, logs: str) -> None:
    """Store running node logs in Redis so partial snapshot can include them (Fix 6)."""
    import redis.asyncio as redis
    from config.settings import get_settings
    try:
        settings = get_settings()
        client = await redis.from_url(settings.redis_url, decode_responses=True)
        await client.set(f"run_logs:{run_id}:{node_id}", logs[-50000:] if len(logs) > 50000 else logs, ex=86400)
        await client.close()
    except Exception as e:
        logger.warning(f"Failed to set run_logs: {e}")


async def _set_redis_cancelled_logs(run_id: str, node_id: str, logs: str) -> None:
    """Store cancelled node logs so _persist_partial_state_on_cancel can merge them (Fix 6)."""
    import json
    import redis.asyncio as redis
    from config.settings import get_settings
    try:
        settings = get_settings()
        client = await redis.from_url(settings.redis_url, decode_responses=True)
        await client.set(f"run_cancelled_logs:{run_id}", json.dumps({node_id: logs[-50000:] if len(logs) > 50000 else logs}), ex=3600)
        await client.close()
    except Exception as e:
        logger.warning(f"Failed to set run_cancelled_logs: {e}")
