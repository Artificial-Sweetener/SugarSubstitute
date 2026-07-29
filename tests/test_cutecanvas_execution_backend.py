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

"""Characterize CuteCanvas work admitted through physical application capacity."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
import time

import pytest
from cutecanvas import (
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionHandle,
    ExecutionRequest,
    ExecutionResource,
    ExecutionRuntime,
    InlineDispatcher,
)

from substitute.infrastructure.execution import (
    CanvasExecutionPolicy,
    CuteCanvasExecutionBackend,
    ThreadPoolAdmission,
)


def test_cutecanvas_backend_runs_one_job_without_sugar_task_lifecycle() -> None:
    """CuteCanvas owns outcomes while SugarSubstitute owns physical admission."""

    admission = _admission(queue_capacity=2)
    runtime = ExecutionRuntime(_backend(admission))
    adopted: list[str] = []
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        handle: ExecutionHandle[str, object] = scope.submit(
            ExecutionRequest(operation="canvas_decode", work=lambda _context: "ready"),
            adopt=adopted.append,
        )

        assert _wait_until(lambda: handle.outcome is not None)
        assert handle.outcome is not None
        assert handle.outcome.result == "ready"
        assert adopted == ["ready"]
    finally:
        runtime.shutdown()
        admission.shutdown(wait=True, cancel_futures=True)


def test_cutecanvas_backend_rejects_saturation_before_acceptance() -> None:
    """Host lane saturation should remain a synchronous CuteCanvas rejection."""

    admission = _admission(queue_capacity=1)
    runtime = ExecutionRuntime(_backend(admission))
    started = Event()
    release = Event()
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        scope.submit(
            ExecutionRequest(
                operation="blocked_canvas_decode",
                work=lambda _context: _wait_for_release(started, release),
            )
        )
        assert started.wait(timeout=1.0)

        with pytest.raises(ExecutionRejected) as caught:
            scope.submit(
                ExecutionRequest(
                    operation="rejected_canvas_decode", work=lambda _: None
                )
            )

        assert caught.value.reason is ExecutionRejectionReason.SATURATED
    finally:
        release.set()
        runtime.shutdown(wait=True)
        admission.shutdown(wait=True, cancel_futures=True)


def test_cutecanvas_backend_cancels_pending_host_work_before_activation() -> None:
    """Cancelling a CuteCanvas scope should remove queued host work safely."""

    admission = _admission(queue_capacity=2)
    runtime = ExecutionRuntime(_backend(admission))
    started = Event()
    release = Event()
    second_started = Event()
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        scope.submit(
            ExecutionRequest(
                operation="blocked_canvas_decode",
                work=lambda _context: _wait_for_release(started, release),
            )
        )
        assert started.wait(timeout=1.0)
        pending: ExecutionHandle[None, object] = scope.submit(
            ExecutionRequest(
                operation="stale_canvas_decode",
                work=lambda _context: second_started.set(),
            )
        )

        assert pending.cancel(reason="superseded")
        assert _wait_until(lambda: pending.outcome is not None)
        assert pending.outcome is not None
        assert pending.outcome.cancellation_reason == "superseded"
        assert not second_started.is_set()
    finally:
        release.set()
        runtime.shutdown(wait=True)
        admission.shutdown(wait=True, cancel_futures=True)


def _admission(*, queue_capacity: int) -> ThreadPoolAdmission:
    """Create one minimal host physical lane for QPane adapter coverage."""

    return ThreadPoolAdmission(
        name="image_decode",
        max_workers=1,
        queue_capacity=queue_capacity,
        thread_name_prefix="test-qpane-host",
    )


def _backend(admission: ThreadPoolAdmission) -> CuteCanvasExecutionBackend:
    """Bind one test admission to native CPU requests."""

    return CuteCanvasExecutionBackend(
        {
            ExecutionResource.NATIVE_CPU: admission,
        },
        policy=CanvasExecutionPolicy(max_accepted=admission.queue_capacity or 256),
    )


def _wait_for_release(started: Event, release: Event) -> None:
    """Block one QPane task until the test permits physical completion."""

    started.set()
    if not release.wait(timeout=1.0):
        raise TimeoutError("Test task was not released before timeout.")


def _wait_until(predicate: Callable[[], bool], *, timeout_seconds: float = 1.0) -> bool:
    """Poll a test predicate without relying on arbitrary execution sleeps."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()
