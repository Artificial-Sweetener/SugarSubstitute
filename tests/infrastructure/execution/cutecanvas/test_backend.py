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

import threading
from threading import Event

import pytest
from cutecanvas import (
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionHandle,
    ExecutionRequest,
    ExecutionRequirements,
    ExecutionResource,
    ExecutionRuntime,
    InlineDispatcher,
)

from substitute.infrastructure.execution import (
    CuteCanvasExecutionBackend,
    HostExecutionPolicy,
    HostExecutionResource,
    HostExecutionScheduler,
)


def test_cutecanvas_backend_runs_one_job_without_sugar_task_lifecycle() -> None:
    """CuteCanvas owns outcomes while SugarSubstitute owns physical admission."""

    scheduler = _scheduler(max_accepted=2)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    adopted: list[str] = []
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        handle: ExecutionHandle[str, object] = scope.submit(
            ExecutionRequest(operation="canvas_decode", work=lambda _context: "ready"),
            adopt=adopted.append,
        )
        completed = Event()
        handle.add_done_callback(lambda _outcome: completed.set())

        assert completed.wait(timeout=1.0)
        assert handle.outcome is not None
        assert handle.outcome.result == "ready"
        assert adopted == ["ready"]
    finally:
        runtime.shutdown()
        scheduler.shutdown(wait=True)


@pytest.mark.parametrize("resource", tuple(ExecutionResource))
def test_every_cutecanvas_resource_runs_on_host_owned_workers(
    resource: ExecutionResource,
) -> None:
    """Keep every current and future canvas resource inside the host."""

    scheduler = _scheduler(max_accepted=2)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        affinity_key = "test-resource-affinity"
        handle: ExecutionHandle[str, object] = scope.submit(
            ExecutionRequest(
                operation=f"resource_{resource.value}",
                requirements=ExecutionRequirements(
                    resource=resource,
                    affinity_key=(
                        affinity_key
                        if resource is ExecutionResource.THREAD_AFFINE_NATIVE
                        else None
                    ),
                ),
                work=lambda _context: threading.current_thread().name,
            )
        )
        completed = Event()
        handle.add_done_callback(lambda _outcome: completed.set())

        assert completed.wait(timeout=1.0)
        assert handle.outcome is not None
        assert handle.outcome.result is not None
        assert handle.outcome.result.startswith("test-canvas-host-")
        assert not handle.outcome.result.startswith("qpane-")
    finally:
        runtime.shutdown()
        scheduler.shutdown(wait=True)


def test_cutecanvas_backend_rejects_saturation_before_acceptance() -> None:
    """Host lane saturation should remain a synchronous CuteCanvas rejection."""

    scheduler = _scheduler(max_accepted=1)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
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
        scheduler.shutdown(wait=True)


def test_cutecanvas_backend_cancels_pending_host_work_before_activation() -> None:
    """Cancelling a CuteCanvas scope should remove queued host work safely."""

    scheduler = _scheduler(max_accepted=2)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
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
        cancelled = Event()
        pending.add_done_callback(lambda _outcome: cancelled.set())

        assert pending.cancel(reason="superseded")
        assert cancelled.wait(timeout=1.0)
        assert pending.outcome is not None
        assert pending.outcome.cancellation_reason == "superseded"
        assert not second_started.is_set()
    finally:
        release.set()
        runtime.shutdown(wait=True)
        scheduler.shutdown(wait=True)


def test_cutecanvas_runtime_reports_the_host_scheduler_snapshot() -> None:
    """Expose the one physical owner's diagnostics through CuteCanvas."""

    scheduler = _scheduler(max_accepted=2)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    try:
        scope = runtime.open_scope(owner_id="document", dispatcher=InlineDispatcher())
        handle: ExecutionHandle[int, object] = scope.submit(
            ExecutionRequest(operation="canvas_diagnostics", work=lambda _context: 7)
        )
        completed = Event()
        handle.add_done_callback(lambda _outcome: completed.set())
        assert completed.wait(timeout=1.0)

        snapshots = runtime.execution_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0].accepted == 0
        assert snapshots[0].pending == 0
        assert snapshots[0].running == 0
        assert snapshots[0].completed == 1
    finally:
        runtime.shutdown()
        scheduler.shutdown(wait=True)


def test_saturated_finalization_runs_after_host_capacity_settles() -> None:
    """Retain native cleanup until the one host scheduler has capacity."""

    scheduler = _scheduler(max_accepted=1)
    runtime = ExecutionRuntime(CuteCanvasExecutionBackend(scheduler))
    blocker_started = Event()
    blocker_release = Event()
    finalized = Event()
    try:
        owner = runtime.open_scope(
            owner_id="document",
            dispatcher=InlineDispatcher(),
        )
        owner.submit(
            ExecutionRequest(
                operation="blocking_owner_work",
                work=lambda _context: _wait_for_release(
                    blocker_started,
                    blocker_release,
                ),
            )
        )
        assert blocker_started.wait(timeout=1.0)
        finalization = owner.open_finalization_scope(owner_id="document:finalization")
        handle: ExecutionHandle[None, object] = finalization.submit(
            ExecutionRequest(
                operation="native_cleanup",
                work=lambda _context: finalized.set(),
            )
        )
        completed = Event()
        handle.add_done_callback(lambda _outcome: completed.set())

        blocker_release.set()

        assert finalized.wait(timeout=1.0)
        assert completed.wait(timeout=1.0)
    finally:
        blocker_release.set()
        runtime.shutdown()
        scheduler.shutdown(wait=True)


def _scheduler(*, max_accepted: int) -> HostExecutionScheduler:
    """Create one deterministic host scheduler for adapter coverage."""

    return HostExecutionScheduler(
        HostExecutionPolicy(
            resource_workers={
                HostExecutionResource.BLOCKING_IO: 1,
                HostExecutionResource.PYTHON_CPU: 1,
                HostExecutionResource.NATIVE_CPU: 1,
                HostExecutionResource.DEVICE: 1,
            },
            affinity_shards=1,
            max_accepted=max_accepted,
            thread_name_prefix="test-canvas-host",
        )
    )


def _wait_for_release(started: Event, release: Event) -> None:
    """Block one QPane task until the test permits physical completion."""

    started.set()
    if not release.wait(timeout=1.0):
        raise TimeoutError("Test task was not released before timeout.")
