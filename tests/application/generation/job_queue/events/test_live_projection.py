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

"""Cover generation-queue live event projection and terminal replay retention."""

from __future__ import annotations


from datetime import datetime, timezone
from pathlib import Path


from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.generation import (
    GenerationFailure,
)
from substitute.application.generation.job_queue_service import (
    GenerationJobQueueService,
    GenerationQueueStateChange,
)
from substitute.application.ports import (
    OutputImageUpdate,
)

from ..queue_service_test_support import (
    _AllocatorRecorder,
    _CallbackRecorder,
    _FakeDispatcher,
    _callbacks,
    _completed,
    _progress_update,
    _service,
    _service_with_allocator,
    _service_with_ids,
    _snapshot,
)


def test_observers_receive_state_snapshots() -> None:
    """Queue observers should receive typed state-change events."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    events: list[GenerationQueueStateChange] = []

    service.add_observer(events.append)
    service.enqueue_snapshot(_snapshot(), _callbacks())

    assert events[0].jobs == ()
    assert [event.change_kind for event in events] == [
        "structural",
        "structural",
        "structural",
        "structural",
    ]
    assert [event.jobs[0].status for event in events[1:]] == [
        "pending",
        "dispatching",
        "running",
    ]


def test_removed_observer_stops_receiving_queue_updates() -> None:
    """Disposed shell observers should not receive later queue updates."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    events: list[GenerationQueueStateChange] = []
    observer = events.append

    service.add_observer(observer)
    service.remove_observer(observer)
    service.enqueue_snapshot(_snapshot(), _callbacks())

    assert len(events) == 1
    assert events[0].jobs == ()
    assert events[0].change_kind == "structural"


def test_output_event_updates_latest_job_output_metadata() -> None:
    """Output callbacks should retain the latest output path before forwarding."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("Output"), _callbacks(recorder))
    first = OutputImageUpdate(
        workflow_id="wf-output",
        workflow_payload={},
        file_path=Path("first.png"),
        node_id="N1",
    )
    second = OutputImageUpdate(
        workflow_id="wf-output",
        workflow_payload={},
        file_path=Path("second.png"),
        node_id="N2",
    )

    dispatcher.callbacks[0].on_output_image(first)
    dispatcher.callbacks[0].on_output_image(second)

    job = service.jobs()[0]
    assert job.last_output_path == Path("second.png")
    assert job.last_output_node_id == "N2"
    assert job.output_count == 2
    assert recorder.outputs == [first, second]


def test_progress_event_updates_active_job_progress() -> None:
    """Progress callbacks should store clamped workflow percent and still forward."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("Progress"), _callbacks(recorder))

    dispatcher.callbacks[0].on_progress(
        _progress_update(workflow_percent=125.0, sampler_percent=None)
    )

    assert service.jobs()[0].progress_percent == 100.0
    assert recorder.progress == [
        _progress_update(workflow_percent=125.0, sampler_percent=None)
    ]


def test_progress_event_clamps_negative_percent() -> None:
    """Negative workflow progress should be clamped before queue display."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    service.enqueue_snapshot(_snapshot("Progress"), _callbacks())

    dispatcher.callbacks[0].on_progress(
        _progress_update(workflow_percent=-5.0, sampler_percent=None)
    )

    assert service.jobs()[0].progress_percent == 0.0


def test_progress_event_ignores_missing_workflow_percent() -> None:
    """Sampler-only progress should not fabricate queue workflow progress."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("Progress"), _callbacks(recorder))

    dispatcher.callbacks[0].on_progress(
        _progress_update(workflow_percent=None, sampler_percent=25.0)
    )

    assert service.jobs()[0].progress_percent is None
    assert recorder.progress == [
        _progress_update(workflow_percent=None, sampler_percent=25.0)
    ]


def test_terminal_job_progress_is_not_forwarded_to_callbacks() -> None:
    """Late progress from a cancelled job should not reach UI callbacks."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    active = service.enqueue_snapshot(_snapshot("Progress"), _callbacks(recorder))

    service.cancel_job(active.job_id)
    dispatcher.callbacks[0].on_progress(
        _progress_update(workflow_percent=42.0, sampler_percent=None)
    )

    assert recorder.progress == []
    assert service.jobs()[0].progress_percent is None


def test_cancel_all_jobs_drops_late_active_progress() -> None:
    """Stop-all should prevent late active-job progress from reopening UI progress."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("First"), _callbacks(recorder))
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())

    service.cancel_all_jobs()
    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="First",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )

    assert recorder.progress == []
    assert [job.progress_percent for job in service.jobs()] == [None, None]


def test_skip_active_job_drops_late_skipped_progress() -> None:
    """Skip should reject old job progress while allowing the replacement job."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    first_recorder = _CallbackRecorder()
    second_recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("First"), _callbacks(first_recorder))
    service.enqueue_snapshot(_snapshot("Second"), _callbacks(second_recorder))

    service.skip_active_job()
    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="First",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=47.0,
            sampler_percent=None,
        )
    )
    replacement_progress = _progress_update(
        workflow_name="Second",
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
        workflow_percent=55.0,
        sampler_percent=None,
    )
    dispatcher.callbacks[1].on_progress(replacement_progress)

    assert first_recorder.progress == []
    assert second_recorder.progress == [replacement_progress]
    assert [job.progress_percent for job in service.jobs()] == [None, 55.0]


def test_progress_identity_must_match_job_run() -> None:
    """A live job should reject progress carrying another run identity."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()
    service.enqueue_snapshot(_snapshot("Progress"), _callbacks(recorder))

    dispatcher.callbacks[0].on_progress(
        _progress_update(
            generation_run_id="old-run",
            prompt_id="old-prompt",
            client_id="old-client",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )

    assert recorder.progress == []
    assert service.jobs()[0].progress_percent is None


def test_queue_keeps_live_output_records_for_current_session_replay() -> None:
    """Queue service should retain output restore records while the row exists."""

    dispatcher = _FakeDispatcher()
    service = GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: "job-1",
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    service.enqueue_snapshot(
        _snapshot("Live", positive_prompt_preview="queue prompt preview"),
        _callbacks(),
    )
    output = OutputImageUpdate(
        workflow_id="wf-live",
        workflow_payload={},
        file_path=Path("live.png"),
        node_id="Save",
        source_key="cube:Save",
        source_label="Save Image",
    )

    dispatcher.callbacks[0].on_output_image(output)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-live"))

    records = service.output_records_for_job("job-1")
    assert [record.output_path for record in records] == [Path("live.png")]
    assert records[0].sequence == 1
    assert records[0].source_key == "cube:Save"
    assert records[0].source_label == "Save Image"
    assert service.job_for_result_replay("job-1") == service.jobs()[0]


def test_removed_terminal_job_drops_live_replay_records() -> None:
    """Removing a queue row should remove its current-session replay records."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    job = service.enqueue_snapshot(_snapshot("Live"), _callbacks())
    output = OutputImageUpdate(
        workflow_id="wf-live",
        workflow_payload={},
        file_path=Path("live.png"),
        node_id="Save",
        source_key="cube:Save",
        source_label="Save Image",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )

    dispatcher.callbacks[0].on_output_image(output)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-live"))
    service.remove_terminal_job(job.job_id)

    assert service.output_records_for_job(job.job_id) == ()
    assert service.job_for_result_replay(job.job_id) is None


def test_failed_active_job_stores_summary_and_detail() -> None:
    """Failure callbacks should preserve raw detail and store compact summaries."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    service.enqueue_snapshot(_snapshot("Failure"), _callbacks())

    dispatcher.callbacks[0].on_failure(
        GenerationFailure(
            stage="listen",
            workflow_id="wf-failure",
            prompt_id="pid-1",
            message="Execution failed",
            detail="ModuleNotFoundError: No module named 'xformers'",
        )
    )

    job = service.jobs()[0]
    assert job.status == "failed"
    assert job.failure_message == "Execution failed"
    assert job.failure_summary is not None
    assert render_source_application_text(job.failure_summary) == "Missing xformers"
    assert job.failure_detail == "ModuleNotFoundError: No module named 'xformers'"


def test_cancelled_active_job_keeps_partial_output_metadata() -> None:
    """Cancelled jobs should preserve any output completed before interruption."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    job = service.enqueue_snapshot(_snapshot("Partial"), _callbacks())
    output = OutputImageUpdate(
        workflow_id="wf-partial",
        workflow_payload={},
        file_path=Path("partial.png"),
        node_id="Save",
    )

    dispatcher.callbacks[0].on_output_image(output)
    service.cancel_job(job.job_id)

    cancelled = service.jobs()[0]
    assert cancelled.status == "cancelled"
    assert cancelled.last_output_path == Path("partial.png")
    assert cancelled.last_output_node_id == "Save"
    assert cancelled.output_count == 1


def test_removing_terminal_job_clears_it_from_visible_queue() -> None:
    """Completed, failed, and cancelled rows should be removable from queue history."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    completed = service.enqueue_snapshot(_snapshot("Completed"), _callbacks())
    pending = service.enqueue_snapshot(_snapshot("Cancelled"), _callbacks())
    service.cancel_job(pending.job_id)
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-completed"))

    service.remove_terminal_job(completed.job_id)
    service.remove_terminal_job(pending.job_id)

    assert service.jobs() == ()


def test_removing_non_terminal_job_is_noop() -> None:
    """Running or pending jobs should use cancel instead of remove."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    running = service.enqueue_snapshot(_snapshot("Running"), _callbacks())
    service.enqueue_snapshot(_snapshot("Pending"), _callbacks())

    service.remove_terminal_job(running.job_id)
    service.remove_terminal_job("job-2")

    assert [job.status for job in service.jobs()] == ["running", "pending"]


def test_terminal_history_prunes_old_completed_jobs_only() -> None:
    """Terminal retention should drop oldest completed rows without touching active work."""

    dispatcher = _FakeDispatcher()
    service = _service_with_ids(
        dispatcher,
        ["job-1", "job-2", "job-3", "job-4"],
        terminal_history_limit=2,
    )

    service.enqueue_snapshot(_snapshot("One"), _callbacks())
    service.enqueue_snapshot(_snapshot("Two"), _callbacks())
    service.enqueue_snapshot(_snapshot("Three"), _callbacks())
    service.enqueue_snapshot(_snapshot("Four"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-one"))
    assert dispatcher.callbacks[1].on_completed is not None
    dispatcher.callbacks[1].on_completed(_completed("wf-two"))
    assert dispatcher.callbacks[2].on_completed is not None
    dispatcher.callbacks[2].on_completed(_completed("wf-three"))

    assert [(job.job_id, job.status) for job in service.jobs()] == [
        ("job-2", "completed"),
        ("job-3", "completed"),
        ("job-4", "running"),
    ]


def test_terminal_history_limit_preserves_pending_jobs() -> None:
    """Terminal retention should never prune pending jobs behind an active job."""

    dispatcher = _FakeDispatcher()
    service = _service_with_ids(
        dispatcher,
        ["job-1", "job-2", "job-3"],
        terminal_history_limit=0,
    )

    service.enqueue_snapshot(_snapshot("Active"), _callbacks())
    service.enqueue_snapshot(_snapshot("PendingA"), _callbacks())
    service.enqueue_snapshot(_snapshot("PendingB"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-active"))

    assert [(job.job_id, job.status) for job in service.jobs()] == [
        ("job-2", "running"),
        ("job-3", "pending"),
    ]


def test_removed_terminal_job_does_not_reuse_output_run_number() -> None:
    """Committed run numbers should stay reserved for the process lifetime."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(dispatcher, allocator)

    first = service.enqueue_snapshot(_snapshot("First"), _callbacks())
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    service.remove_terminal_job(first.job_id)
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())

    assert [request.output_run_number for request in dispatcher.requests] == [1, 2]
