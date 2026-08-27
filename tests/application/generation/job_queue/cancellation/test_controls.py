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

"""Cover generation-queue cancellation and active-job controls."""

from __future__ import annotations


from substitute.application.generation.job_queue_service import (
    GenerationJobLifecycleEvent,
)

from ..queue_service_test_support import (
    _AllocatorRecorder,
    _FakeDispatcher,
    _callbacks,
    _completed,
    _service,
    _service_with_allocator,
    _snapshot,
)


def test_cancelling_pending_job_prevents_dispatch() -> None:
    """Pending cancellation should be local and should skip later dispatch."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    pending = service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.cancel_job(pending.job_id)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    assert [job.status for job in service.jobs()] == ["completed", "cancelled"]
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]
    assert dispatcher.interrupt_calls == 0


def test_cancelling_pending_job_does_not_commit_output_number() -> None:
    """Pending cancellation should not consume a committed output number."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7])
    service = _service_with_allocator(dispatcher, allocator)

    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    pending = service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.cancel_job(pending.job_id)

    cancelled = service.jobs()[1]
    assert cancelled.status == "cancelled"
    assert cancelled.output_run_number is None
    assert [request.output_run_number for request in dispatcher.requests] == [7]


def test_cancelling_active_job_interrupts_and_dispatches_next() -> None:
    """Active cancellation should call interrupt and continue queued work."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    active = service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.cancel_job(active.job_id)

    assert [job.status for job in service.jobs()] == ["cancelled", "running"]
    assert dispatcher.interrupt_calls == 1
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_skip_active_job_cancels_running_job_and_dispatches_next() -> None:
    """Skip should cancel the active job and continue with the next pending job."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.skip_active_job()

    assert [job.status for job in service.jobs()] == ["cancelled", "running"]
    assert dispatcher.interrupt_calls == 1
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_scene_lifecycle_observer_distinguishes_skip_cancel_and_completion() -> None:
    """Lifecycle events should carry scene metadata and user cancellation intent."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    events: list[GenerationJobLifecycleEvent] = []
    service.add_lifecycle_observer(events.append)

    service.enqueue_snapshot(
        _snapshot(
            "First",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=3,
        ),
        _callbacks(),
    )
    service.enqueue_snapshot(
        _snapshot(
            "Second",
            scene_run_id="run-1",
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=3,
        ),
        _callbacks(),
    )
    service.enqueue_snapshot(
        _snapshot(
            "Third",
            scene_run_id="run-1",
            scene_key="street",
            scene_title="Street",
            scene_order=2,
            scene_count=3,
        ),
        _callbacks(),
    )

    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    service.skip_active_job()
    service.cancel_all_jobs()

    scene_events = [
        (event.action, event.job.snapshot.scene_key, event.job.status)
        for event in events
        if event.job.snapshot.scene_run_id == "run-1"
        and event.action in {"completed", "skipped", "cancelled"}
    ]
    assert scene_events == [
        ("completed", "portrait", "completed"),
        ("skipped", "cafe", "cancelled"),
        ("cancelled", "street", "cancelled"),
    ]


def test_skip_active_job_noops_when_queue_is_idle() -> None:
    """Skip should not interrupt or dispatch when no job is active."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.skip_active_job()

    assert service.jobs() == ()
    assert dispatcher.interrupt_calls == 0
    assert dispatcher.requests == []


def test_cancel_all_jobs_cancels_active_and_pending_without_dispatching_next() -> None:
    """Stop-all should cancel queued work without starting another job."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())
    service.cancel_all_jobs()

    assert [job.status for job in service.jobs()] == [
        "cancelled",
        "cancelled",
        "cancelled",
    ]
    assert dispatcher.interrupt_calls == 1
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]


def test_cancel_all_jobs_noops_when_queue_is_empty() -> None:
    """Stop-all should be inert when no queued jobs exist."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.cancel_all_jobs()

    assert service.jobs() == ()
    assert dispatcher.interrupt_calls == 0
    assert dispatcher.requests == []


def test_queue_availability_is_false_after_cancel_all_jobs() -> None:
    """Cancelled queue history should not remain actionable."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.cancel_all_jobs()

    assert service.has_active_job() is False
    assert service.has_cancellable_jobs() is False
