"""
Tests for suspended state propagation in the node executor.
"""
import pytest


GRAPH_JSON = {
    "nodes": [
        {"id": "wait1", "node_type_id": "wait", "name": "Wait Node", "config": {"channel": "approval", "mode": "signal"}},
        {"id": "downstream1", "node_type_id": "custom-python", "name": "Downstream", "config": {}},
        {"id": "independent1", "node_type_id": "custom-python", "name": "Independent", "config": {}},
    ],
    "edges": [
        {"source": "wait1", "target": "downstream1"},
    ],
}


class TestHasSuspendedInput:
    def test_returns_true_when_upstream_suspended(self):
        from services.temporal.activities.node_executor import _has_suspended_input
        state = {
            "node_outputs": {
                "wait1": {"__suspended__": True, "channel": "approval"},
            }
        }
        assert _has_suspended_input(state, "downstream1", GRAPH_JSON) is True

    def test_returns_false_when_upstream_not_suspended(self):
        from services.temporal.activities.node_executor import _has_suspended_input
        state = {
            "node_outputs": {
                "wait1": {"output": "some_result"},
            }
        }
        assert _has_suspended_input(state, "downstream1", GRAPH_JSON) is False

    def test_returns_false_for_independent_node(self):
        from services.temporal.activities.node_executor import _has_suspended_input
        state = {
            "node_outputs": {
                "wait1": {"__suspended__": True, "channel": "approval"},
            }
        }
        # independent1 has no edge from wait1
        assert _has_suspended_input(state, "independent1", GRAPH_JSON) is False

    def test_returns_false_when_no_upstream(self):
        from services.temporal.activities.node_executor import _has_suspended_input
        state = {"node_outputs": {}}
        assert _has_suspended_input(state, "wait1", GRAPH_JSON) is False


class TestWaitNodeFunction:
    @pytest.mark.asyncio
    async def test_wait_node_returns_suspended_marker(self):
        """Wait node function should return __suspended__: True output."""
        from services.temporal.activities.node_executor import create_node_function
        from unittest.mock import patch, AsyncMock, MagicMock

        node_data = {
            "id": "wait1",
            "node_type_id": "wait",
            "name": "Wait Node",
            "config": {"channel": "approval", "mode": "signal"},
        }

        with patch("services.signals.wait_service.persist_wait_state", AsyncMock(return_value=MagicMock())), \
             patch("database.connection.SessionLocal", MagicMock(return_value=MagicMock())):
            func = create_node_function(node_data, "run1", {}, graph_json=GRAPH_JSON)
            state = {"node_outputs": {}, "node_inputs": {}, "node_name_map": {}}
            result = await func(state)

        assert result["node_outputs"]["wait1"]["__suspended__"] is True
        assert result["node_outputs"]["wait1"]["channel"] == "approval"

    @pytest.mark.asyncio
    async def test_wait_node_skips_when_already_resolved(self):
        """Wait node function should skip if node already has a real (non-suspended) output."""
        from services.temporal.activities.node_executor import create_node_function

        node_data = {
            "id": "wait1",
            "node_type_id": "wait",
            "name": "Wait Node",
            "config": {"channel": "approval", "mode": "signal"},
        }

        func = create_node_function(node_data, "run1", {}, graph_json=GRAPH_JSON)
        # Node already has real output (from resume)
        state = {
            "node_outputs": {"wait1": {"signal": "approved", "data": {}}},
            "node_inputs": {},
            "node_name_map": {},
        }
        result = await func(state)
        # Should return just node_name_map (skip logic)
        assert "node_outputs" not in result or result.get("node_name_map")


class TestSuspendedPropagation:
    @pytest.mark.asyncio
    async def test_downstream_node_propagates_suspended(self):
        """Downstream node should propagate __suspended__ when upstream is suspended."""
        from services.temporal.activities.node_executor import create_node_function

        node_data = {
            "id": "downstream1",
            "node_type_id": "custom-python",
            "name": "Downstream",
            "config": {"code": "def main(inputs): return inputs"},
        }

        func = create_node_function(node_data, "run1", {}, graph_json=GRAPH_JSON)
        state = {
            "node_outputs": {
                "wait1": {"__suspended__": True, "channel": "approval"},
            },
            "node_inputs": {},
            "node_name_map": {},
        }
        result = await func(state)
        # Should propagate suspended
        assert result["node_outputs"]["downstream1"]["__suspended__"] is True
