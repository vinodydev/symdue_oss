# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for issue12: snapshot sanitization for Postgres jsonb.

Postgres rejects strings containing \\x00 (NULL byte) inside jsonb columns.
LLM outputs occasionally contain such bytes. The sanitizer at
node_executor.py:_sanitize_for_jsonb removes them recursively.
"""


def test_strips_null_byte_from_top_level_string():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    assert _sanitize_for_jsonb("hello\x00world") == "helloworld"


def test_no_change_for_clean_string():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    assert _sanitize_for_jsonb("hello world") == "hello world"


def test_recursive_dict():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    inp = {"a": "x\x00y", "b": {"c": "ok", "d": "p\x00q"}}
    out = _sanitize_for_jsonb(inp)
    assert out == {"a": "xy", "b": {"c": "ok", "d": "pq"}}


def test_recursive_list():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    inp = ["a", "b\x00c", {"k": "v\x00"}]
    out = _sanitize_for_jsonb(inp)
    assert out == ["a", "bc", {"k": "v"}]


def test_passthrough_non_string_types():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    assert _sanitize_for_jsonb(42) == 42
    assert _sanitize_for_jsonb(3.14) == 3.14
    assert _sanitize_for_jsonb(True) is True
    assert _sanitize_for_jsonb(None) is None


def test_does_not_mutate_input():
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    inp = {"key": "with\x00null"}
    _sanitize_for_jsonb(inp)
    # Original should still have the null byte.
    assert "\x00" in inp["key"]


def test_handles_realistic_llm_output_shape():
    """A simulated LLM output structure with deeply nested strings, lists,
    and a stray null byte buried in one node's output."""
    from services.temporal.activities.node_executor import _sanitize_for_jsonb
    snapshot = {
        "node_outputs": {
            "abc-123": {"output": "iteration 1 result"},
            "def-456": {"output": "iteration 2 with\x00stray byte"},
            "ghi-789": {"output": {"answers": ["clean", "also\x00not clean", "fine"]}},
        },
        "node_iteration_outputs": {
            "abc-123": [
                {"step": 1, "ts": 100, "output": {"text": "ok"}},
                {"step": 2, "ts": 101, "output": {"text": "with\x00bad byte"}},
            ],
        },
    }
    out = _sanitize_for_jsonb(snapshot)
    assert out["node_outputs"]["def-456"]["output"] == "iteration 2 withstray byte"
    assert out["node_outputs"]["ghi-789"]["output"]["answers"][1] == "alsonot clean"
    assert out["node_iteration_outputs"]["abc-123"][1]["output"]["text"] == "withbad byte"
    # Verify no null bytes survive
    import json
    assert "\x00" not in json.dumps(out)
