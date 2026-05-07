# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for log preservation in node outputs and snapshots.

Verifies that logs from Python node execution (Docker container stdout/stderr)
are stored in node_outputs and propagated to the run snapshot, while downstream
nodes still receive only the raw output values (not the metadata).
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.temporal.activities.node_executor import (
    _aggregate_node_inputs,
    create_node_function,
    _execute_manual_topo,
    execute_python_node_activity,
    execute_input_node_activity,
)


# ════════════════════════════════════════════════════════════
# Test: _aggregate_node_inputs strips logs/error metadata
# ════════════════════════════════════════════════════════════

class TestAggregateNodeInputs:
    """Ensure _aggregate_node_inputs extracts raw output from entries that include logs."""

    def test_extracts_output_from_entry_with_logs(self):
        """When node_outputs stores {"output": ..., "logs": ...}, downstream gets just the output."""
        state = {
            "node_outputs": {
                "node-1": {"output": "hello world", "logs": "some container logs here"},
            },
            "node_name_map": {"node-1": "fetch_data"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"fetch_data": "hello world"}

    def test_extracts_output_from_entry_with_logs_and_error(self):
        """When node_outputs stores {"output": ..., "logs": ..., "error": ...}, downstream gets just the output."""
        state = {
            "node_outputs": {
                "node-1": {"output": None, "logs": "error logs", "error": "something failed"},
            },
            "node_name_map": {"node-1": "fetch_data"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"fetch_data": None}

    def test_extracts_output_from_entry_without_logs(self):
        """When node_outputs stores {"output": ...} with no logs, downstream gets just the output."""
        state = {
            "node_outputs": {
                "node-1": {"output": {"key": "value"}},
            },
            "node_name_map": {"node-1": "fetch_data"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"fetch_data": {"key": "value"}}

    def test_handles_dict_output_with_nested_output_key(self):
        """User returns {"output": "x", "data": 123} — downstream gets the full user dict."""
        state = {
            "node_outputs": {
                "node-1": {
                    "output": {"output": "x", "data": 123},
                    "logs": "container logs",
                },
            },
            "node_name_map": {"node-1": "fetch_data"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"fetch_data": {"output": "x", "data": 123}}

    def test_handles_string_output(self):
        """When a node returns a plain string."""
        state = {
            "node_outputs": {
                "node-1": {"output": "just a string", "logs": "log line 1\nlog line 2"},
            },
            "node_name_map": {"node-1": "input_node"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"input_node": "just a string"}

    def test_handles_error_output_without_output_key(self):
        """Error entries from exception path don't have 'output' key — pass through as-is."""
        error_entry = {
            "error": "execution failed",
            "type": "RuntimeError",
            "traceback": "...",
            "node_id": "node-1",
            "node_name": "bad_node",
            "node_type": "custom-python",
        }
        state = {
            "node_outputs": {"node-1": error_entry},
            "node_name_map": {"node-1": "bad_node"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        assert result == {"bad_node": error_entry}

    def test_skips_name_keyed_duplicates(self):
        """Entries stored by node name (duplicates) should be skipped."""
        state = {
            "node_outputs": {
                "node-1": {"output": "hello", "logs": "logs"},
                "fetch_data": {"output": "hello", "logs": "logs"},  # name-keyed duplicate
            },
            "node_name_map": {"node-1": "fetch_data"},
        }
        result = _aggregate_node_inputs(state, "node-2", {})
        # Should only have one entry, keyed by name
        assert result == {"fetch_data": "hello"}

    def test_multiple_upstream_nodes(self):
        """Multiple upstream nodes, each with logs — downstream gets all raw outputs."""
        state = {
            "node_outputs": {
                "node-1": {"output": "data_a", "logs": "log a"},
                "node-2": {"output": {"price": 42}, "logs": "log b"},
                "node_a": {"output": "data_a", "logs": "log a"},       # name duplicate
                "node_b": {"output": {"price": 42}, "logs": "log b"},  # name duplicate
            },
            "node_name_map": {"node-1": "node_a", "node-2": "node_b"},
        }
        result = _aggregate_node_inputs(state, "node-3", {})
        assert result == {"node_a": "data_a", "node_b": {"price": 42}}


# ════════════════════════════════════════════════════════════
# Test: Python node activity returns logs
# ════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestPythonNodeLogsPreserved:
    """Test that execute_python_node_activity returns logs in its result."""

    @pytest.mark.asyncio
    async def test_python_node_returns_logs(self):
        """Docker executor returns logs — they should be in the activity result."""
        node_id = "node-1"
        config = {"code": "def main(inputs): return 'hello'", "requirements": ""}
        inputs = {"value": "test"}
        run_id = "test-run-123"

        mock_result = {
            "output": "hello",
            "output_type": "text",
            "error": None,
            "logs": "Starting execution...\nDone.",
        }

        with patch("services.docker.executor.DockerExecutor") as mock_docker_class:
            mock_executor = MagicMock()
            mock_executor.execute_python_node = AsyncMock(return_value=mock_result)
            mock_docker_class.return_value = mock_executor

            with patch("services.temporal.activities.node_executor.publish_node_status"):
                result = await execute_python_node_activity(node_id, config, inputs, run_id)

        assert result["logs"] == "Starting execution...\nDone."
        assert result["output"] == "hello"

    @pytest.mark.asyncio
    async def test_python_node_error_preserves_logs(self):
        """When Docker executor returns an error, logs should still be in the result."""
        node_id = "node-1"
        config = {"code": "def main(): pass", "requirements": ""}
        inputs = {}
        run_id = "test-run-123"

        mock_result = {
            "output": None,
            "output_type": "text",
            "error": "main() takes 0 positional arguments but 1 was given",
            "logs": "pip install ...\nPlaywright banner\nTraceback...",
        }

        with patch("services.docker.executor.DockerExecutor") as mock_docker_class:
            mock_executor = MagicMock()
            mock_executor.execute_python_node = AsyncMock(return_value=mock_result)
            mock_docker_class.return_value = mock_executor

            with patch("services.temporal.activities.node_executor.publish_node_status"):
                result = await execute_python_node_activity(node_id, config, inputs, run_id)

        assert "logs" in result
        assert "Traceback" in result["logs"]


# ════════════════════════════════════════════════════════════
# Test: Manual topo execution preserves logs in state
# ════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestManualTopoLogsInState:
    """Test that _execute_manual_topo stores logs in node_outputs."""

    @pytest.mark.asyncio
    async def test_manual_topo_stores_logs_in_node_outputs(self):
        """After manual topo execution, node_outputs should include logs."""
        graph_json = {
            "nodes": [
                {
                    "id": "node-1",
                    "node_type_id": "custom-python",
                    "name": "my_python_node",
                    "config": {
                        "code": "def main(inputs): return 'hello'",
                        "requirements": "",
                    },
                }
            ],
            "edges": [],
        }

        mock_result = {
            "output": "hello",
            "output_type": "text",
            "error": None,
            "logs": "Container started\nRunning script\nDone",
        }

        with patch(
            "services.temporal.activities.node_executor.execute_python_node_activity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with patch("services.temporal.activities.node_executor.publish_node_status"):
                with patch("temporalio.activity.heartbeat"):
                    final_state = await _execute_manual_topo(graph_json, {}, "test-run")

        node_output = final_state["node_outputs"]["node-1"]
        assert isinstance(node_output, dict)
        assert node_output["output"] == "hello"
        assert node_output["logs"] == "Container started\nRunning script\nDone"

    @pytest.mark.asyncio
    async def test_manual_topo_stores_output_without_logs(self):
        """Nodes that don't produce logs should still work (e.g. input nodes)."""
        graph_json = {
            "nodes": [
                {
                    "id": "node-1",
                    "node_type_id": "input",
                    "name": "my_input",
                    "config": {"value": "test_value"},
                }
            ],
            "edges": [],
        }

        mock_result = {
            "output": "test_value",
            "output_type": "text",
        }

        with patch(
            "services.temporal.activities.node_executor.execute_input_node_activity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with patch("services.temporal.activities.node_executor.publish_node_status"):
                with patch("temporalio.activity.heartbeat"):
                    final_state = await _execute_manual_topo(graph_json, {}, "test-run")

        node_output = final_state["node_outputs"]["node-1"]
        assert isinstance(node_output, dict)
        assert node_output["output"] == "test_value"
        # No logs key should be present since the result had no logs
        assert "logs" not in node_output

    @pytest.mark.asyncio
    async def test_manual_topo_downstream_gets_clean_output(self):
        """Downstream nodes should receive clean output, not the metadata wrapper."""
        graph_json = {
            "nodes": [
                {
                    "id": "node-1",
                    "node_type_id": "input",
                    "name": "my_input",
                    "config": {"value": "upstream_value"},
                },
                {
                    "id": "node-2",
                    "node_type_id": "custom-python",
                    "name": "my_processor",
                    "config": {
                        "code": "def main(inputs): return inputs",
                        "requirements": "",
                    },
                },
            ],
            "edges": [
                {"source": "node-1", "target": "node-2"},
            ],
        }

        input_result = {"output": "upstream_value", "output_type": "text"}
        python_result = {
            "output": {"my_input": "upstream_value"},
            "output_type": "text",
            "error": None,
            "logs": "Processing...\nDone.",
        }

        call_count = {"input": 0, "python": 0}
        captured_python_inputs = {}

        async def mock_input_activity(*args, **kwargs):
            call_count["input"] += 1
            return input_result

        async def mock_python_activity(node_id, config, node_inputs, run_id):
            call_count["python"] += 1
            captured_python_inputs.update(node_inputs)
            return python_result

        with patch(
            "services.temporal.activities.node_executor.execute_input_node_activity",
            side_effect=mock_input_activity,
        ):
            with patch(
                "services.temporal.activities.node_executor.execute_python_node_activity",
                side_effect=mock_python_activity,
            ):
                with patch("services.temporal.activities.node_executor.publish_node_status"):
                    with patch("temporalio.activity.heartbeat"):
                        final_state = await _execute_manual_topo(
                            graph_json, {}, "test-run"
                        )

        # The Python node should have received clean inputs (no logs metadata)
        assert "my_input" in captured_python_inputs
        # The input should be the raw value, not {"output": ..., "logs": ...}
        assert captured_python_inputs["my_input"] == "upstream_value"

        # But the snapshot should have logs
        python_output = final_state["node_outputs"]["node-2"]
        assert "logs" in python_output
        assert python_output["logs"] == "Processing...\nDone."


# ════════════════════════════════════════════════════════════
# Test: Snapshot structure matches expected format
# ════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestSnapshotStructure:
    """Test that the final state (snapshot) has the expected structure with logs."""

    @pytest.mark.asyncio
    async def test_snapshot_has_logs_for_python_nodes(self):
        """The snapshot's node_outputs should contain logs for Python nodes."""
        graph_json = {
            "nodes": [
                {
                    "id": "fb53ea6d-7bc3-4d2b-a79c-5e5cc91a4ddc",
                    "node_type_id": "custom-python",
                    "name": "node_custom-python_fb53ea6d",
                    "config": {
                        "code": "def main(data): return {'output': 'Empty'}",
                        "requirements": "",
                    },
                }
            ],
            "edges": [],
        }

        mock_result = {
            "output": {"output": "Empty"},
            "output_type": "text",
            "error": None,
            "logs": "--- Execution Started ---\nStarting browser session...\nNavigating to chart...\nDone",
        }

        with patch(
            "services.temporal.activities.node_executor.execute_python_node_activity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with patch("services.temporal.activities.node_executor.publish_node_status"):
                with patch("temporalio.activity.heartbeat"):
                    final_state = await _execute_manual_topo(graph_json, {}, "test-run")

        node_id = "fb53ea6d-7bc3-4d2b-a79c-5e5cc91a4ddc"
        node_name = "node_custom-python_fb53ea6d"

        # Both ID and name entries should exist
        assert node_id in final_state["node_outputs"]
        assert node_name in final_state["node_outputs"]

        # Both should have the same content
        id_entry = final_state["node_outputs"][node_id]
        name_entry = final_state["node_outputs"][node_name]
        assert id_entry == name_entry

        # Should have output and logs
        assert id_entry["output"] == {"output": "Empty"}
        assert id_entry["logs"] == "--- Execution Started ---\nStarting browser session...\nNavigating to chart...\nDone"

