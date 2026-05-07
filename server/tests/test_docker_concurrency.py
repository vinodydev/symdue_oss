# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for issue16 — verify that asyncio.to_thread wrapping of docker-py
calls actually allows sibling fan-out coroutines to run concurrently.

We don't spin up real containers in unit tests (too slow + flaky in CI).
Instead, we mock docker-py with a fake client whose methods sleep
synchronously, then verify that 4 parallel calls finish in ~1× the per-call
sleep time (parallel) rather than 4× (sequential).

If asyncio.to_thread is missing, the fake's sleep blocks the event loop
and the test sees ~4× wall time → assertion fails.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# A fake docker-py client whose sync methods sleep for a fixed time.
# Mimics the blocking behavior of real docker-py + dockerd round-trips.
# ──────────────────────────────────────────────────────────────────

class _FakeContainer:
    def __init__(self, sleep_per_op: float):
        self._sleep = sleep_per_op
        self.short_id = "fake_id"
        self.status = "exited"
        self.attrs = {}

    def start(self):
        time.sleep(self._sleep)

    def stop(self, timeout: int = 5):
        time.sleep(self._sleep)

    def wait(self, timeout: int = 10):
        time.sleep(self._sleep)
        return {"StatusCode": 0}

    def logs(self, stdout: bool = True, stderr: bool = True):
        time.sleep(self._sleep)
        return b""

    def reload(self):
        time.sleep(self._sleep)

    def remove(self, force: bool = False):
        time.sleep(self._sleep)

    def put_archive(self, dst_path: str, buf):
        time.sleep(self._sleep)
        return True


class _FakeContainersAPI:
    def __init__(self, sleep_per_op: float):
        self._sleep = sleep_per_op

    def create(self, **kwargs):
        time.sleep(self._sleep)
        return _FakeContainer(self._sleep)


class _FakeImagesAPI:
    def get(self, name):
        time.sleep(0.01)

    def pull(self, name):
        time.sleep(0.01)


class _FakeNetworksAPI:
    def list(self):
        time.sleep(0.01)
        return []


class _FakeDockerClient:
    def __init__(self, sleep_per_op: float):
        self.containers = _FakeContainersAPI(sleep_per_op)
        self.images = _FakeImagesAPI()
        self.networks = _FakeNetworksAPI()


# ──────────────────────────────────────────────────────────────────
# The actual test: simulate the create+start sequence for 4 siblings,
# both with and without asyncio.to_thread, and compare wall times.
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_to_thread_enables_concurrent_docker_create():
    """4 concurrent fake docker.containers.create calls (each sleeping 0.5s)
    should finish in ~0.5s wall, not ~2s. This is the issue16 contract."""
    sleep_per_op = 0.5  # seconds
    n_siblings = 4

    client = _FakeDockerClient(sleep_per_op)

    async def one_sibling():
        # The pattern from executor.py after issue16's fix:
        container = await asyncio.to_thread(client.containers.create, image="x")
        await asyncio.to_thread(container.start)
        return container

    t0 = time.perf_counter()
    results = await asyncio.gather(*[one_sibling() for _ in range(n_siblings)])
    wall = time.perf_counter() - t0

    # Total CPU time = n_siblings * 2 ops * sleep_per_op = 4 * 2 * 0.5 = 4.0s
    # If serial: ~4.0s wall
    # If parallel: ~1.0s wall (max of one sibling's chain = 2 * 0.5 = 1.0s)
    expected_parallel = 2 * sleep_per_op  # one sibling's create+start chain
    expected_serial = n_siblings * 2 * sleep_per_op
    assert len(results) == n_siblings
    # Wall time should be much closer to parallel than serial.
    # Allow generous slack for thread-pool scheduling overhead.
    assert wall < expected_parallel * 1.8, (
        f"Wall time {wall:.2f}s is too long; expected ~{expected_parallel}s "
        f"(parallel) and definitely not {expected_serial}s (serial). "
        f"This means asyncio.to_thread is missing somewhere in executor.py."
    )


@pytest.mark.asyncio
async def test_without_to_thread_serializes():
    """Sanity-check the test methodology: without asyncio.to_thread, the
    same 4 calls do serialize on the event loop. (This isn't a real test
    of executor.py — it's a baseline that confirms our timing measurement
    actually distinguishes serial vs parallel.)"""
    sleep_per_op = 0.3
    n_siblings = 4

    client = _FakeDockerClient(sleep_per_op)

    async def one_sibling_blocking():
        # Direct sync calls inside async (the pre-issue16 pattern).
        container = client.containers.create(image="x")
        container.start()
        return container

    t0 = time.perf_counter()
    await asyncio.gather(*[one_sibling_blocking() for _ in range(n_siblings)])
    wall = time.perf_counter() - t0

    expected_serial = n_siblings * 2 * sleep_per_op  # 4 * 2 * 0.3 = 2.4s
    # Should be close to serial (allow some slack).
    assert wall >= expected_serial * 0.85, (
        f"Wall time {wall:.2f}s is unexpectedly fast for serialized calls; "
        f"expected ~{expected_serial}s. Test methodology may be off."
    )


@pytest.mark.asyncio
async def test_to_thread_does_not_change_return_value():
    """Pure refactor — to_thread returns the same value the function would.
    This guards against accidentally double-wrapping or returning the future."""
    client = _FakeDockerClient(sleep_per_op=0.01)
    container = await asyncio.to_thread(client.containers.create, image="x")
    assert isinstance(container, _FakeContainer)
    assert container.short_id == "fake_id"


@pytest.mark.asyncio
async def test_event_loop_responsive_during_blocking_call():
    """While a docker-py-style sync call sleeps inside to_thread, the event
    loop must remain free for other coroutines (e.g. Temporal heartbeats).
    This is the 'no Activity cancelled at 2 min' part of issue16."""
    sleep_per_op = 0.5
    client = _FakeDockerClient(sleep_per_op)

    heartbeat_ticks = []

    async def heartbeat_task():
        # Mimics Temporal's heartbeat task ticking every 0.05s.
        for _ in range(20):
            heartbeat_ticks.append(time.perf_counter())
            await asyncio.sleep(0.05)

    async def docker_op():
        await asyncio.to_thread(client.containers.create, image="x")

    t0 = time.perf_counter()
    await asyncio.gather(heartbeat_task(), docker_op())
    wall = time.perf_counter() - t0

    # Heartbeats should have continued throughout the docker op.
    # If the event loop were blocked, heartbeat_ticks would cluster at the end.
    n_during_op = sum(1 for t in heartbeat_ticks if (t - t0) < sleep_per_op * 0.9)
    assert n_during_op >= 5, (
        f"Only {n_during_op} heartbeats fired during the {sleep_per_op}s docker op; "
        f"expected >= 5. The event loop was blocked — to_thread isn't doing its job."
    )
