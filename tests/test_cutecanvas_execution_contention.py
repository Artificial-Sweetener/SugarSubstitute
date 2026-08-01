#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Abuse SugarSubstitute's resource-aware CuteCanvas execution policy."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Lock

import pytest
from cutecanvas import (
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionRequest,
    ExecutionRequirements,
    ExecutionResource,
    ExecutionRuntime,
    ExecutionUrgency,
    InlineDispatcher,
)

from substitute.infrastructure.execution import (
    CuteCanvasExecutionBackend,
    HostExecutionPolicy,
    HostExecutionRequirements,
    HostExecutionResource,
    HostExecutionScheduler,
    ThreadPoolAdmission,
)


def test_canvas_work_isolated_from_saturated_image_decode() -> None:
    """Let interactive rendering progress while application image decode is blocked."""

    image_decode = _admission("image-decode", workers=1, capacity=2)
    scheduler = _canvas_scheduler(native_workers=1)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    decode_started = Event()
    decode_release = Event()
    canvas_completed = Event()
    try:
        image_decode.submit(
            lambda: _block_until_released(decode_started, decode_release)
        )
        assert decode_started.wait(timeout=1.0)
        scope = runtime.open_scope(owner_id="contention", dispatcher=InlineDispatcher())

        scope.submit(
            ExecutionRequest(
                operation="interactive_detail_render",
                work=lambda _context: canvas_completed.set(),
                requirements=ExecutionRequirements(
                    resource=ExecutionResource.NATIVE_CPU,
                    urgency=ExecutionUrgency.INTERACTIVE,
                ),
            )
        )

        assert canvas_completed.wait(timeout=1.0)
        assert not decode_release.is_set()
    finally:
        decode_release.set()
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)
        image_decode.shutdown(wait=True, cancel_futures=True)


def test_interactive_canvas_work_overtakes_queued_background_work() -> None:
    """Schedule urgency ahead of FIFO order once a physical worker becomes free."""

    scheduler = _canvas_scheduler(native_workers=1)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    blocker_started = Event()
    blocker_release = Event()
    settled = Event()
    order: list[str] = []
    try:
        scope = runtime.open_scope(owner_id="priority", dispatcher=InlineDispatcher())
        scope.submit(
            ExecutionRequest(
                operation="block_native",
                work=lambda _context: _block_until_released(
                    blocker_started,
                    blocker_release,
                ),
            )
        )
        assert blocker_started.wait(timeout=1.0)
        scope.submit(
            ExecutionRequest(
                operation="background_grid",
                work=lambda _context: order.append("background"),
                requirements=ExecutionRequirements(
                    resource=ExecutionResource.NATIVE_CPU,
                    urgency=ExecutionUrgency.BACKGROUND,
                ),
            )
        )
        scope.submit(
            ExecutionRequest(
                operation="interactive_detail",
                work=lambda _context: order.append("interactive"),
                requirements=ExecutionRequirements(
                    resource=ExecutionResource.NATIVE_CPU,
                    urgency=ExecutionUrgency.INTERACTIVE,
                ),
            ),
            adopt=lambda _result: settled.set(),
        )

        blocker_release.set()
        assert settled.wait(timeout=1.0)
        assert _wait_until(lambda: len(order) == 2)
        assert order == ["interactive", "background"]
    finally:
        blocker_release.set()
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)


def test_canvas_work_wakes_after_shared_host_capacity_is_released() -> None:
    """Do not strand accepted canvas work behind another host producer."""

    scheduler = _canvas_scheduler(native_workers=1)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    blocker_started = Event()
    blocker_release = Event()
    canvas_completed = Event()
    try:
        scheduler.submit_detached(
            lambda: _block_until_released(blocker_started, blocker_release),
            operation="host_native_blocker",
            requirements=HostExecutionRequirements(
                resource=HostExecutionResource.NATIVE_CPU,
                urgency_rank=10,
            ),
        )
        assert blocker_started.wait(timeout=1.0)
        scope = runtime.open_scope(
            owner_id="shared-capacity",
            dispatcher=InlineDispatcher(),
        )
        scope.submit(
            ExecutionRequest(
                operation="canvas_after_host_work",
                work=lambda _context: canvas_completed.set(),
            )
        )

        blocker_release.set()

        assert canvas_completed.wait(timeout=1.0)
    finally:
        blocker_release.set()
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)


def test_canvas_maximum_concurrency_is_enforced_per_resource_identity() -> None:
    """Never exceed a request's declared concurrency under a hostile burst."""

    scheduler = _canvas_scheduler(native_workers=4)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    release = Event()
    reached_limit = Event()
    counter_lock = Lock()
    active = 0
    maximum_active = 0

    def work(_context: object) -> None:
        """Track active work until the fixture releases the burst."""

        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
            if active == 2:
                reached_limit.set()
        if not release.wait(timeout=1.0):
            raise TimeoutError("concurrency burst was not released")
        with counter_lock:
            active -= 1

    try:
        scope = runtime.open_scope(
            owner_id="concurrency", dispatcher=InlineDispatcher()
        )
        requirements = ExecutionRequirements(
            resource=ExecutionResource.NATIVE_CPU,
            resource_id="grid-render-products",
            maximum_concurrency=2,
        )
        for index in range(8):
            scope.submit(
                ExecutionRequest(
                    operation=f"grid_render_{index}",
                    work=work,
                    requirements=requirements,
                )
            )

        assert reached_limit.wait(timeout=1.0)
        with counter_lock:
            assert active == 2
            assert maximum_active == 2
        assert scheduler.snapshot().running == 2
    finally:
        release.set()
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)


def test_canvas_retained_payload_budget_rejects_before_acceptance() -> None:
    """Reject a payload estimate that exceeds the host's bounded memory policy."""

    scheduler = _canvas_scheduler(
        native_workers=1,
        max_accepted=4,
        max_retained_bytes=32,
    )
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    try:
        scope = runtime.open_scope(owner_id="retained", dispatcher=InlineDispatcher())
        with pytest.raises(ExecutionRejected) as caught:
            scope.submit(
                ExecutionRequest(
                    operation="oversized_pyramid",
                    work=lambda _context: None,
                    requirements=ExecutionRequirements(
                        estimated_retained_bytes=33,
                    ),
                )
            )

        assert caught.value.reason is ExecutionRejectionReason.SATURATED
        assert ("limit", "retained_bytes") in caught.value.details
    finally:
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)


def _canvas_scheduler(
    *,
    native_workers: int,
    max_accepted: int = 256,
    max_retained_bytes: int = 512 * 1024 * 1024,
) -> HostExecutionScheduler:
    """Create one isolated deterministic host scheduler."""

    return HostExecutionScheduler(
        HostExecutionPolicy(
            resource_workers={
                HostExecutionResource.BLOCKING_IO: 1,
                HostExecutionResource.PYTHON_CPU: 1,
                HostExecutionResource.NATIVE_CPU: native_workers,
                HostExecutionResource.DEVICE: 1,
            },
            affinity_shards=1,
            max_accepted=max_accepted,
            max_retained_bytes=max_retained_bytes,
            thread_name_prefix="test-canvas-host",
        )
    )


def _admission(
    name: str,
    *,
    workers: int,
    capacity: int,
) -> ThreadPoolAdmission:
    """Create one bounded physical lane."""

    return ThreadPoolAdmission(
        name=name,
        max_workers=workers,
        queue_capacity=capacity,
        thread_name_prefix=f"test-{name}",
    )


def _block_until_released(started: Event, release: Event) -> None:
    """Block one worker until the fixture explicitly releases it."""

    started.set()
    if not release.wait(timeout=1.0):
        raise TimeoutError("blocked execution was not released")


def _wait_until(predicate: Callable[[], bool], *, timeout_seconds: float = 1.0) -> bool:
    """Poll execution state with a bounded deadline."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()
