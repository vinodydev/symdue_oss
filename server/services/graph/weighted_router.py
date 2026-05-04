"""
Weighted router - Implements edge weight routing logic (0.0-1.0)
This is the core "Weighted Intelligence" feature.

Condition router - Routes based on condition node's true/false output;
only the matching branch's targets are executed.
"""
from typing import Dict, Any, List, Union


def normalize_condition_output(output: Any) -> bool:
    """
    Normalize a condition node's return value to a boolean.
    - bool: use as-is
    - dict with "branch" key (string "true"/"false"): map to True/False
    - dict with "condition" key (bool): use that
    - otherwise: Python truthiness
    """
    if isinstance(output, bool):
        return output
    if isinstance(output, dict):
        if "branch" in output:
            b = output["branch"]
            if isinstance(b, str) and b.lower() == "false":
                return False
            if isinstance(b, str) and b.lower() == "true":
                return True
        if "condition" in output:
            return bool(output["condition"])
    return bool(output)


def create_condition_router(
    condition_node_id: str,
    true_targets: List[str],
    false_targets: List[str],
) -> callable:
    """
    Create a router for a condition node. Reads node_outputs[condition_node_id],
    normalizes to boolean; returns the target(s) for the true branch or the false branch.
    Returns a single target or list of targets (LangGraph supports both).
    """
    def condition_router(state: Dict[str, Any]) -> Union[str, List[str]]:
        node_outputs = state.get("node_outputs", {})
        raw = node_outputs.get(condition_node_id)
        # Handle wrapped output: node_outputs[id] may be {"output": ...}
        if isinstance(raw, dict) and "output" in raw and len(raw) == 1:
            raw = raw["output"]
        elif isinstance(raw, dict) and "output" in raw:
            raw = raw["output"]
        result = normalize_condition_output(raw)
        targets = true_targets if result else false_targets
        if not targets:
            # No edge on this branch: LangGraph needs a node; we use END via terminal handling.
            # Compiler must not add conditional_edges when one branch has no targets;
            # instead it adds an edge to END for that branch. So we must return something.
            # The compiler will add edges from condition node: one conditional edge that
            # goes to either true_targets or false_targets. If one list is empty we cannot
            # return nothing. So the compiler should add a synthetic END node or use END.
            # LangGraph add_conditional_edges requires returning a key that exists in the
            # target_map. So we need the compiler to add a sentinel like __end__ to the
            # target_map when a branch has no targets, and we return that.
            return "__end__"
        if len(targets) == 1:
            return targets[0]
        return targets

    return condition_router


def create_weighted_router(
    source_node_id: str,
    edges: List[Dict[str, Any]]
) -> callable:
    """
    Create a weighted routing function for LangGraph conditional edges.
    
    This implements the "Weighted Intelligence" feature where edge weights (0.0-1.0)
    act as confidence signals for downstream nodes.
    
    Routing Strategy:
    1. **All weights = 1.0**: Route to all targets (parallel execution)
    2. **Single high weight**: Route to highest weight edge
    3. **Multiple high weights**: Route to all edges above threshold (parallel)
    4. **Probability-based**: Use weights as probabilities for random routing
    5. **Zero weights**: Skip edges with weight = 0.0
    
    Args:
        source_node_id: ID of source node
        edges: List of edges with 'target' and 'weight' keys
    
    Returns:
        Router function that returns target node ID(s) based on weights
    """
    # Configuration
    PARALLEL_THRESHOLD = 0.7  # Edges above this execute in parallel
    MIN_WEIGHT = 0.1  # Minimum weight to consider
    
    def weighted_router(state: Dict[str, Any]) -> Union[str, List[str]]:
        """
        Route based on edge weights.
        
        Returns:
            - Single string: Target node ID for sequential execution
            - List of strings: Target node IDs for parallel execution
        """
        # Get source node output (for potential conditional routing)
        node_outputs = state.get("node_outputs", {})
        source_output = node_outputs.get(source_node_id, {})
        
        # Filter out zero-weight edges
        valid_edges = [e for e in edges if e["weight"] >= MIN_WEIGHT]
        
        if not valid_edges:
            # All edges have zero weight - skip routing
            raise ValueError(f"No valid edges from node {source_node_id}")
        
        # Strategy 1: All weights are 1.0 - parallel execution
        if all(e["weight"] == 1.0 for e in valid_edges):
            return [e["target"] for e in valid_edges]
        
        # Strategy 2: Filter high-weight edges (above threshold)
        high_weight_edges = [
            e for e in valid_edges
            if e["weight"] >= PARALLEL_THRESHOLD
        ]
        
        if len(high_weight_edges) > 1:
            # Multiple high-weight edges - execute in parallel
            return [e["target"] for e in high_weight_edges]
        
        # Strategy 3: Single high-weight edge - route to it
        if high_weight_edges:
            return high_weight_edges[0]["target"]
        
        # Strategy 4: Probability-based routing for medium weights
        # Use weights as probabilities (normalized)
        total_weight = sum(e["weight"] for e in valid_edges)
        
        if total_weight == 0:
            # Fallback: route to first edge
            return valid_edges[0]["target"]
        
        # Normalize weights to probabilities
        probabilities = [e["weight"] / total_weight for e in valid_edges]
        
        # Use max probability for deterministic routing
        # (For non-deterministic, could use random.choices)
        max_prob_idx = probabilities.index(max(probabilities))
        return valid_edges[max_prob_idx]["target"]
    
    return weighted_router

