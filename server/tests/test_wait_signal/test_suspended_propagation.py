# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for suspended state propagation helpers in the node executor.
"""
import pytest


GRAPH_JSON = {
    "nodes": [
        {"id": "wait1", "node_type_id": "wait", "name": "Wait Node",
         "config": {"channel": "approval", "mode": "signal"}},
        {"id": "downstream1", "node_type_id": "custom-python", "name": "Downstream", "config": {}},
        {"id": "independent1", "node_type_id": "custom-python", "name": "Independent", "config": {}},
    ],
    "edges": [
        {"source": "wait1", "target": "downstream1"},
    ],
}


class TestHasNoSuspendedInput:
    def test_has_no_suspended_input(self):
        """A node with no upstream (or no suspended upstream) returns False."""
        from services.temporal.activities.node_executor import _has_suspended_input

        # independent1 has no incoming edges, so it never sees suspended input
        state = {
            "node_outputs": {
                "wait1": {"__suspended__": True, "channel": "approval"},
            }
        }
        assert _has_suspended_input(state, "independent1", GRAPH_JSON) is False

    def test_has_no_suspended_input_when_upstream_not_suspended(self):
        """A node whose upstream output does NOT have __suspended__ returns False."""
        from services.temporal.activities.node_executor import _has_suspended_input

        state = {
            "node_outputs": {
                "wait1": {"output": "some_result"},
            }
        }
        assert _has_suspended_input(state, "downstream1", GRAPH_JSON) is False


class TestHasSuspendedInput:
    def test_has_suspended_input(self):
        """A node whose upstream output contains __suspended__: True returns True."""
        from services.temporal.activities.node_executor import _has_suspended_input

        state = {
            "node_outputs": {
                "wait1": {"__suspended__": True, "channel": "approval"},
            }
        }
        assert _has_suspended_input(state, "downstream1", GRAPH_JSON) is True

    def test_has_suspended_input_empty_outputs(self):
        """With empty node_outputs, no node has a suspended input."""
        from services.temporal.activities.node_executor import _has_suspended_input

        state = {"node_outputs": {}}
        assert _has_suspended_input(state, "wait1", GRAPH_JSON) is False
        assert _has_suspended_input(state, "downstream1", GRAPH_JSON) is False
