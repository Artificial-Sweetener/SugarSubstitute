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

"""Cover generation-queue dispatch lifecycle and pending-order mutation."""

from __future__ import annotations


from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
)
from substitute.application.ports import (
    CubeExecutionTiming,
    GenerationExecutionTiming,
)

from ..queue_service_test_support import (
    _AllocatorRecorder,
    _CallbackRecorder,
    _FakeDispatcher,
    _ReconcilingDispatcher,
    _callbacks,
    _completed,
    _scheduled_service,
    _service,
    _service_with_allocator,
    _snapshot,
)


def test_queue_availability_is_false_when_queue_is_empty() -> None:
    """Empty queues should not expose active or cancellable work."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    assert service.has_active_job() is False
    assert service.has_cancellable_jobs() is False


def test_queue_availability_is_true_for_active_running_job() -> None:
    """A running queued job should be active and cancellable."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("Active"), _callbacks())

    assert service.has_active_job() is True
    assert service.has_cancellable_jobs() is True


def test_queue_availability_remains_true_with_active_and_pending_jobs() -> None:
    """Queued pending work behind an active job should remain cancellable."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("Active"), _callbacks())
    service.enqueue_snapshot(_snapshot("Pending"), _callbacks())

    assert service.has_active_job() is True
    assert service.has_cancellable_jobs() is True


def test_second_job_waits_until_first_completes() -> None:
    """Queue should dispatch exactly one job at a time."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())

    assert [job.status for job in service.jobs()] == ["running", "pending"]
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]

    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    assert [job.status for job in service.jobs()] == ["completed", "running"]
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_timing_event_updates_running_job_before_completion_callback() -> None:
    """Queue timing should be stored before the wrapped completion callback renders."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    observed_on_completion: list[float | None] = []
    callbacks = _callbacks(recorder)
    callbacks = GenerationCallbacks(
        randomize_seeds=callbacks.randomize_seeds,
        on_run_started=callbacks.on_run_started,
        on_progress=callbacks.on_progress,
        on_model_load_progress=callbacks.on_model_load_progress,
        on_preview=callbacks.on_preview,
        on_output_image=callbacks.on_output_image,
        on_failure=callbacks.on_failure,
        on_timing=callbacks.on_timing,
        on_completed=lambda _event: observed_on_completion.append(
            service.jobs()[0].execution_duration_ms
        ),
    )

    service.enqueue_snapshot(_snapshot("First"), callbacks)
    timing = GenerationExecutionTiming(
        workflow_id="wf-first",
        prompt_id="pid-1",
        job_duration_ms=308000.0,
        cube_timings=(
            CubeExecutionTiming(
                cube_alias="First",
                source_key="wf-first:N1",
                duration_ms=850.0,
            ),
        ),
    )

    assert dispatcher.callbacks[0].on_timing is not None
    dispatcher.callbacks[0].on_timing(timing)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    job = service.jobs()[0]
    assert job.status == "completed"
    assert job.execution_duration_ms == 308000.0
    assert recorder.timing == [timing]
    assert observed_on_completion == [308000.0]
    assert (
        service.cube_execution_duration_ms(
            workflow_id="wf-first",
            source_key="wf-first:N1",
        )
        == 850.0
    )


def test_late_timing_event_updates_completed_job() -> None:
    """Late timing should refresh a completed queue row instead of being dropped."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    assert dispatcher.callbacks[0].on_timing is not None
    dispatcher.callbacks[0].on_timing(
        GenerationExecutionTiming(
            workflow_id="wf-first",
            prompt_id="pid-1",
            job_duration_ms=1200.0,
        )
    )

    job = service.jobs()[0]
    assert job.status == "completed"
    assert job.execution_duration_ms == 1200.0


def test_listener_completion_dispatches_next_job_through_scheduler() -> None:
    """Listener-thread completion should not dispatch the next job inline."""

    dispatcher = _FakeDispatcher()
    scheduled: list[object] = []
    service = _scheduled_service(dispatcher, scheduled)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    assert [job.status for job in service.jobs()] == ["running", "pending"]
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]
    assert len(scheduled) == 1

    scheduled_callback = scheduled.pop()
    assert callable(scheduled_callback)
    scheduled_callback()

    assert [job.status for job in service.jobs()] == ["completed", "running"]
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_failed_active_job_dispatches_next_pending_job() -> None:
    """Failure callback should mark the active job failed and continue dispatch."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()

    service.enqueue_snapshot(_snapshot("First"), _callbacks(recorder))
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    dispatcher.callbacks[0].on_failure(
        GenerationFailure(
            stage="listen",
            workflow_id="wf-first",
            prompt_id="pid-1",
            message="boom",
        )
    )

    assert [job.status for job in service.jobs()] == ["failed", "running"]
    assert service.jobs()[0].failure_message == "boom"
    assert service.jobs()[0].failure_summary == "boom"
    assert recorder.failures[0].message == "boom"
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_dispatch_unavailable_holds_pending_job_after_active_failure() -> None:
    """A Comfy outage should preserve pending work after the active job fails."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.set_dispatch_available(False)
    dispatcher.callbacks[0].on_failure(
        GenerationFailure(
            stage="listen",
            workflow_id="wf-first",
            prompt_id="pid-1",
            message="Comfy disconnected",
        )
    )

    assert [job.status for job in service.jobs()] == ["failed", "pending"]
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]

    service.set_dispatch_available(True)

    assert [job.status for job in service.jobs()] == ["failed", "running"]
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Second",
    ]


def test_dispatch_unavailable_holds_new_work_until_comfy_recovers() -> None:
    """Work enqueued during an outage should dispatch only after recovery."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    service.set_dispatch_available(False)

    service.enqueue_snapshot(_snapshot("Pending"), _callbacks())

    assert [job.status for job in service.jobs()] == ["pending"]
    assert dispatcher.requests == []

    service.set_dispatch_available(True)

    assert [job.status for job in service.jobs()] == ["running"]
    assert [request.workflow_name for request in dispatcher.requests] == ["Pending"]


def test_listener_disconnect_gates_queue_before_active_failure_advances() -> None:
    """Typed listener disconnects should hold pending work without a monitor race."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    connection_losses: list[str] = []

    def handle_connection_lost() -> None:
        """Record the outage and gate dispatch through its public policy port."""

        connection_losses.append("lost")
        service.set_dispatch_available(False)

    service.set_connection_lost_handler(handle_connection_lost)
    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())

    dispatcher.callbacks[0].on_failure(
        GenerationFailure(
            stage="listen",
            workflow_id="wf-first",
            prompt_id="pid-1",
            message="Comfy disconnected",
            connection_lost=True,
        )
    )

    assert connection_losses == ["lost"]
    assert [job.status for job in service.jobs()] == ["failed", "pending"]
    assert [request.workflow_name for request in dispatcher.requests] == ["First"]


def test_dispatch_reconciles_with_comfy_queue_when_available() -> None:
    """Queue dispatch should inspect Comfy queue state for external work logging."""

    dispatcher = _ReconcilingDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot(), _callbacks())

    assert dispatcher.get_queue_calls == 1


def test_queue_availability_stays_active_after_completion_dispatches_next() -> None:
    """Completion should preserve active availability when another job dispatches."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    assert service.has_active_job() is True
    assert service.has_cancellable_jobs() is True


def test_reordering_pending_jobs_changes_dispatch_order() -> None:
    """Only pending jobs should be reordered for future dispatch."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    second = service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())
    service.move_pending_job("job-3", 0)
    service.move_pending_job(second.job_id, 1)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "First",
        "Third",
        "Second",
    ]
    assert [request.workflow_name for request in dispatcher.requests] == [
        "First",
        "Third",
    ]


def test_reordering_pending_jobs_changes_committed_output_number_order() -> None:
    """Reordered pending jobs should commit numbers in their new dispatch order."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([23])
    service = _service_with_allocator(dispatcher, allocator)

    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.move_pending_job("job-3", 0)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-shared"))

    running_job = next(job for job in service.jobs() if job.status == "running")
    assert running_job.job_id == "job-3"
    assert running_job.output_run_number == 24
    assert [request.output_run_number for request in dispatcher.requests] == [23, 24]


def test_output_number_commit_failure_continues_to_later_pending_job() -> None:
    """A dispatch-time output number failure should fail one job and continue."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7])
    service = _service_with_allocator(dispatcher, allocator)

    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    service.enqueue_snapshot(_snapshot("Shared"), _callbacks())
    allocator.failures_remaining = 1
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-shared"))

    jobs_by_id = {job.job_id: job for job in service.jobs()}
    assert jobs_by_id["job-2"].status == "failed"
    assert jobs_by_id["job-2"].output_run_number is None
    assert jobs_by_id["job-3"].status == "running"
    assert jobs_by_id["job-3"].output_run_number == 8
    assert [request.output_run_number for request in dispatcher.requests] == [7, 8]


def test_reordering_non_pending_jobs_is_noop() -> None:
    """Only pending rows should be accepted by the reorder service API."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("Running"), _callbacks())
    service.enqueue_snapshot(_snapshot("Pending"), _callbacks())
    service.move_pending_job("job-1", 0)
    assert dispatcher.callbacks[0].on_failure is not None
    dispatcher.callbacks[0].on_failure(
        GenerationFailure(
            stage="listen",
            workflow_id="wf-running",
            prompt_id="pid-1",
            message="failed",
        )
    )
    service.move_pending_job("job-1", 0)

    assert [job.job_id for job in service.jobs()] == ["job-1", "job-2"]
    assert [job.status for job in service.jobs()] == ["failed", "running"]
