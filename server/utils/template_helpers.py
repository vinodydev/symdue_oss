# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Template helper functions for node and workflow templates.

Provides utilities for:
- Extracting environment variables from Python code
- Classifying environment variables (workflow vs node level)
- Identifying input/output nodes
- Serializing nodes and edges for template storage
- Detecting circular dependencies
"""
import re
import ast
from typing import Set, Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import WorkflowNode, WorkflowEdge


def extract_env_vars_from_code(python_code: str) -> Set[str]:
    """
    Extract environment variable names from Python code.
    
    Looks for patterns like:
    - os.environ.get("VAR_NAME")
    - os.environ["VAR_NAME"]
    - os.getenv("VAR_NAME")
    - os.environ.get('VAR_NAME')
    
    Args:
        python_code: Python source code string
        
    Returns:
        Set of environment variable names found
    """
    if not python_code:
        return set()
    
    env_vars = set()
    
    # Pattern 1: os.environ.get("VAR_NAME") or os.getenv("VAR_NAME")
    pattern1 = r'os\.(?:environ\.get|getenv)\(["\']([A-Z_][A-Z0-9_]*)["\']'
    matches = re.findall(pattern1, python_code)
    env_vars.update(matches)
    
    # Pattern 2: os.environ["VAR_NAME"] or os.environ['VAR_NAME']
    pattern2 = r'os\.environ\[["\']([A-Z_][A-Z0-9_]*)["\']'
    matches = re.findall(pattern2, python_code)
    env_vars.update(matches)
    
    # Pattern 3: Try AST parsing for more complex cases
    try:
        tree = ast.parse(python_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    isinstance(node.func.value, ast.Attribute) and
                    node.func.value.attr == 'environ' and
                    node.func.attr in ('get', 'getenv')):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        env_vars.add(node.args[0].value)
            elif isinstance(node, ast.Subscript):
                if (isinstance(node.value, ast.Attribute) and
                    node.value.attr == 'environ'):
                    if isinstance(node.slice, ast.Constant):
                        env_vars.add(node.slice.value)
    except SyntaxError:
        # If code is invalid, fall back to regex only
        pass
    except Exception:
        # Any other parsing error, fall back to regex
        pass
    
    return env_vars


def is_workflow_level_var(env_var: str) -> bool:
    """
    Determine if an environment variable should be workflow-level.
    
    Workflow-level vars are typically:
    - Storage connections (S3_BUCKET, DATABASE_URL, REDIS_URL)
    - API keys shared across nodes (API_KEY, OPENAI_API_KEY)
    - Service endpoints (API_BASE_URL, WEBHOOK_BASE_URL)
    
    Args:
        env_var: Environment variable name
        
    Returns:
        True if should be workflow-level, False if node-level
    """
    workflow_patterns = [
        r'^(S3|DATABASE|REDIS|MONGO|CHROMA|MINIO|STORAGE)',
        r'_(URL|HOST|ENDPOINT|BUCKET|CONNECTION|CONFIG)$',
        r'^(API|OPENAI|ANTHROPIC|GOOGLE)_',
        r'^WEBHOOK_',
    ]
    
    for pattern in workflow_patterns:
        if re.match(pattern, env_var, re.IGNORECASE):
            return True
    
    return False


def is_node_level_var(env_var: str) -> bool:
    """
    Determine if an environment variable should be node-level.
    
    Node-level vars are typically:
    - Node-specific timeouts (NODE_TIMEOUT, TIMEOUT)
    - Node-specific retries (NODE_RETRIES, RETRIES)
    - Node-specific intervals (NODE_CHECK_INTERVAL, POLL_INTERVAL)
    
    Args:
        env_var: Environment variable name
        
    Returns:
        True if should be node-level, False if workflow-level
    """
    node_patterns = [
        r'^NODE_',
        r'_(TIMEOUT|RETRIES|INTERVAL|DELAY|LIMIT)$',
    ]
    
    for pattern in node_patterns:
        if re.match(pattern, env_var, re.IGNORECASE):
            return True
    
    return False


def identify_input_nodes(nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> List[WorkflowNode]:
    """
    Identify input nodes (nodes with no incoming edges).
    
    Args:
        nodes: List of all nodes in workflow
        edges: List of all edges in workflow
        
    Returns:
        List of input nodes
    """
    if not nodes:
        return []
    
    target_node_ids = {edge.target_node_id for edge in edges if edge.deleted_at is None}
    input_nodes = [node for node in nodes if node.deleted_at is None and node.id not in target_node_ids]
    return input_nodes


def identify_output_nodes(nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> List[WorkflowNode]:
    """
    Identify output nodes (nodes with no outgoing edges).
    
    Args:
        nodes: List of all nodes in workflow
        edges: List of all edges in workflow
        
    Returns:
        List of output nodes
    """
    if not nodes:
        return []
    
    source_node_ids = {edge.source_node_id for edge in edges if edge.deleted_at is None}
    output_nodes = [node for node in nodes if node.deleted_at is None and node.id not in source_node_ids]
    return output_nodes


def build_input_ports(input_nodes: List[WorkflowNode]) -> List[Dict[str, Any]]:
    """
    Build input port definitions from input nodes.
    
    Args:
        input_nodes: List of input nodes
        
    Returns:
        List of input port definitions
    """
    ports = []
    for node in input_nodes:
        ports.append({
            "node_id": str(node.id),
            "node_name": node.name,
            "node_type_id": node.node_type_id,
            "description": f"Input from {node.name}",
        })
    return ports


def build_output_ports(output_nodes: List[WorkflowNode]) -> List[Dict[str, Any]]:
    """
    Build output port definitions from output nodes.
    
    Args:
        output_nodes: List of output nodes
        
    Returns:
        List of output port definitions
    """
    ports = []
    for node in output_nodes:
        ports.append({
            "node_id": str(node.id),
            "node_name": node.name,
            "node_type_id": node.node_type_id,
            "description": f"Output from {node.name}",
        })
    return ports


def serialize_node(node: WorkflowNode) -> Dict[str, Any]:
    """
    Serialize a WorkflowNode to a dictionary for template storage.
    
    Args:
        node: WorkflowNode instance
        
    Returns:
        Dictionary representation of node
    """
    return {
        "id": str(node.id),
        "name": node.name,
        "node_type_id": node.node_type_id,
        "ui_x": node.ui_x,
        "ui_y": node.ui_y,
        "config": node.config or {},
        "node_config": getattr(node, 'node_config', {}) or {},
    }


def serialize_edge(edge: WorkflowEdge) -> Dict[str, Any]:
    """
    Serialize a WorkflowEdge to a dictionary for template storage.
    
    Args:
        edge: WorkflowEdge instance
        
    Returns:
        Dictionary representation of edge
    """
    result = {
        "id": str(edge.id),
        "source_node_id": str(edge.source_node_id),
        "target_node_id": str(edge.target_node_id),
        "weight": getattr(edge, 'weight', 1.0),
    }
    if getattr(edge, 'source_handle', None) is not None:
        result["source_handle"] = edge.source_handle
    return result


def detect_circular_dependency(
    parent_workflow_id: str,
    sub_workflow_id: str,
    visited: Optional[set] = None,
    db: Optional[Session] = None
) -> bool:
    """
    Detect circular dependencies in workflow nesting.
    
    Args:
        parent_workflow_id: ID of parent workflow
        sub_workflow_id: ID of sub-workflow to check
        visited: Set of visited workflow IDs (for recursion)
        db: Database session
        
    Returns:
        True if circular dependency detected, False otherwise
    """
    from database.models import Workflow, WorkflowNode
    
    if visited is None:
        visited = set()
    
    if sub_workflow_id in visited:
        return True  # Circular!
    
    if sub_workflow_id == parent_workflow_id:
        return True  # Self-reference!
    
    visited.add(sub_workflow_id)
    
    # Check if sub-workflow has workflow nodes
    if db:
        sub_workflow = db.query(Workflow).filter_by(id=sub_workflow_id).first()
        if sub_workflow:
            for node in sub_workflow.nodes:
                if node.node_type_id == "workflow_node":
                    workflow_id = node.config.get("workflow_id")
                    if workflow_id:
                        if detect_circular_dependency(
                            parent_workflow_id,
                            str(workflow_id),
                            visited.copy(),
                            db
                        ):
                            return True
    
    return False

