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

"""Cover generation-queue enqueue transactions."""

from __future__ import annotations


from collections.abc import Callable
from datetime import datetime, timezone, tzinfo
from typing import Self, cast

from pytest import MonkeyPatch


from substitute.application.generation import (
    PreparedGenerationRequest,
)
from substitute.application.generation.job_queue_service import (
    GenerationQueueBatchEntry,
    GenerationJobLifecycleEvent,
    GenerationJobQueueService,
    GenerationQueueStateChange,
)
import substitute.application.generation.job_queue_service as queue_module
from substitute.domain.generation import (
    GenerationJobSnapshot,
)
from substitute.domain.workflow import WorkflowState

from ..queue_service_test_support import (
    _CallbackRecorder,
    _CapturingSubmitter,
    _FakeDispatcher,
    _callbacks,
    _completed,
    _owner_scheduled_service,
    _service,
    _snapshot,
)


def test_enqueue_dispatches_first_snapshot_immediately() -> None:
    """First pending job should dispatch through the prepared generation path."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()

    job = service.enqueue_snapshot(_snapshot(), _callbacks(recorder))

    assert job.job_id == "job-1"
    assert service.jobs()[0].status == "running"
    assert service.jobs()[0].prompt_id == "pid-1"
    assert dispatcher.requests == [
        PreparedGenerationRequest(
            workflow_id="wf-workflow",
            workflow_name="Workflow",
            sugar_script_text='use "cube" as Workflow',
            output_job_started_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )
    ]
    assert recorder.cleared == []


def test_enqueue_preserves_snapshot_workflow_for_generation_staging() -> None:
    """Queue dispatch should retain the captured semantic staging authority."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    staging_workflow = WorkflowState()
    snapshot = GenerationJobSnapshot(
        workflow_id="wf-staging",
        workflow_name="Staging",
        sugar_script_text='use "cube" as Staging',
        workflow=staging_workflow,
    )

    service.enqueue_snapshot(snapshot, _callbacks())

    assert cast(object, dispatcher.requests[0].workflow) is staging_workflow


def test_enqueue_snapshots_batches_state_notification_and_dispatch_schedule() -> None:
    """Batch enqueue should publish queue state once and schedule dispatch once."""

    dispatcher = _FakeDispatcher()
    scheduled: list[Callable[[], None]] = []
    service = _owner_scheduled_service(dispatcher, scheduled)
    events: list[GenerationQueueStateChange] = []
    lifecycle_events: list[GenerationJobLifecycleEvent] = []
    service.add_observer(events.append)
    service.add_lifecycle_observer(lifecycle_events.append)
    snapshots = (
        _snapshot(
            "Scene A",
            scene_run_id="scene-run",
            scene_key="a",
            scene_title="Scene A",
            scene_order=0,
            scene_count=3,
        ),
        _snapshot(
            "Scene B",
            scene_run_id="scene-run",
            scene_key="b",
            scene_title="Scene B",
            scene_order=1,
            scene_count=3,
        ),
        _snapshot(
            "Scene C",
            scene_run_id="scene-run",
            scene_key="c",
            scene_title="Scene C",
            scene_order=2,
            scene_count=3,
        ),
    )

    jobs = service.enqueue_snapshots(snapshots, _callbacks())

    assert [job.job_id for job in jobs] == ["job-1", "job-2", "job-3"]
    assert [job.snapshot.workflow_name for job in jobs] == [
        "Scene A",
        "Scene B",
        "Scene C",
    ]
    assert [job.snapshot.scene_key for job in jobs] == ["a", "b", "c"]
    assert len(events) == 2
    assert events[0].jobs == ()
    assert events[0].change_kind == "structural"
    assert [job.job_id for job in events[1].jobs] == ["job-1", "job-2", "job-3"]
    assert [job.status for job in events[1].jobs] == ["pending", "pending", "pending"]
    assert events[1].change_kind == "structural"
    assert [event.action for event in lifecycle_events] == [
        "enqueued",
        "enqueued",
        "enqueued",
    ]
    assert [event.job.job_id for event in lifecycle_events] == [
        "job-1",
        "job-2",
        "job-3",
    ]
    assert len(scheduled) == 1
    assert dispatcher.requests == []


def test_enqueue_snapshots_empty_batch_is_noop() -> None:
    """Empty batch enqueue should avoid observer, lifecycle, and dispatch work."""

    dispatcher = _FakeDispatcher()
    scheduled: list[Callable[[], None]] = []
    service = _owner_scheduled_service(dispatcher, scheduled)
    events: list[GenerationQueueStateChange] = []
    lifecycle_events: list[GenerationJobLifecycleEvent] = []
    service.add_observer(events.append)
    service.add_lifecycle_observer(lifecycle_events.append)
    events.clear()

    jobs = service.enqueue_snapshots((), _callbacks())

    assert jobs == ()
    assert events == []
    assert lifecycle_events == []
    assert scheduled == []
    assert service.jobs() == ()


def test_enqueue_snapshot_single_uses_same_transaction_semantics() -> None:
    """Single enqueue should retain one state notification and one dispatch schedule."""

    dispatcher = _FakeDispatcher()
    scheduled: list[Callable[[], None]] = []
    service = _owner_scheduled_service(dispatcher, scheduled)
    events: list[GenerationQueueStateChange] = []
    lifecycle_events: list[GenerationJobLifecycleEvent] = []
    service.add_observer(events.append)
    service.add_lifecycle_observer(lifecycle_events.append)
    events.clear()

    job = service.enqueue_snapshot(_snapshot("Single"), _callbacks())

    assert job.job_id == "job-1"
    assert [event.jobs[0].job_id for event in events] == ["job-1"]
    assert [event.change_kind for event in events] == ["structural"]
    assert [event.action for event in lifecycle_events] == ["enqueued"]
    assert len(scheduled) == 1
    assert dispatcher.requests == []


def test_enqueue_snapshot_entries_preserve_per_job_callbacks() -> None:
    """Batch entries should keep distinct callbacks for each queued job."""

    dispatcher = _FakeDispatcher()
    scheduled: list[Callable[[], None]] = []
    service = _owner_scheduled_service(dispatcher, scheduled)
    first_recorder = _CallbackRecorder()
    second_recorder = _CallbackRecorder()

    service.enqueue_snapshot_entries(
        (
            GenerationQueueBatchEntry(
                snapshot=_snapshot("First"),
                callbacks=_callbacks(first_recorder),
            ),
            GenerationQueueBatchEntry(
                snapshot=_snapshot("Second"),
                callbacks=_callbacks(second_recorder),
            ),
        )
    )

    scheduled.pop()()
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    assert dispatcher.callbacks[1].on_completed is not None
    dispatcher.callbacks[1].on_completed(_completed("wf-second"))

    assert first_recorder.completed == [_completed("wf-first")]
    assert second_recorder.completed == [_completed("wf-second")]


def test_default_dispatch_clock_uses_local_aware_time(
    monkeypatch: MonkeyPatch,
) -> None:
    """Default dispatch timestamps should use the local OS timezone."""

    class _LocalDateTime(datetime):
        """Expose whether the queue asks Python for local or UTC time."""

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            """Return a local wall-clock time and reject explicit timezone requests."""

            if tz is not None:
                raise AssertionError("Default output timestamps must use local time.")
            return cls(2026, 5, 12, 23, 30, 0)

    monkeypatch.setattr(queue_module, "datetime", _LocalDateTime)
    dispatcher = _FakeDispatcher()
    service = GenerationJobQueueService(dispatcher)

    service.enqueue_snapshot(_snapshot(), _callbacks())

    assert (
        dispatcher.requests[0].output_job_started_at
        == _LocalDateTime(2026, 5, 12, 23, 30, 0).astimezone()
    )


def test_enqueue_with_dispatch_submitter_returns_before_dispatch_runs() -> None:
    """Queued dispatch should be submitted to execution without blocking enqueue."""

    dispatcher = _FakeDispatcher()
    submitter = _CapturingSubmitter()
    service = GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: "job-1",
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        dispatch_submitter=submitter,
        owner_thread_scheduler=lambda callback: callback(),
    )

    job = service.enqueue_snapshot(_snapshot(), _callbacks())

    assert job.status == "dispatching"
    assert dispatcher.requests == []
    assert len(submitter.requests) == 1

    result = submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_success(result)

    assert dispatcher.requests
    assert service.jobs()[0].status == "running"


def test_shutdown_cancels_inflight_dispatch_and_closes_submitter() -> None:
    """Queue shutdown should cancel scoped dispatch without publishing late failure."""

    dispatcher = _FakeDispatcher()
    submitter = _CapturingSubmitter()
    recorder = _CallbackRecorder()
    close_calls: list[str] = []
    service = GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: "job-1",
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        dispatch_submitter=submitter,
        close_dispatch_submitter=lambda: close_calls.append("closed"),
        owner_thread_scheduler=lambda callback: callback(),
    )

    job = service.enqueue_snapshot(_snapshot(), _callbacks(recorder))
    assert job.status == "dispatching"
    assert len(submitter.handles) == 1
    assert submitter.handles[0].state == "pending"

    service.shutdown()
    service.shutdown()

    assert close_calls == ["closed"]
    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "generation_queue_shutdown"
    assert submitter.handles[0].state == "cancelled"
    assert dispatcher.requests == []
    assert recorder.failures == []


def test_enqueue_dispatches_scene_metadata_with_prepared_request() -> None:
    """Scene snapshot metadata should survive queue dispatch boundaries."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(
        _snapshot(
            "Scene",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        _callbacks(),
    )

    assert dispatcher.requests[0].scene_run_id == "run-1"
    assert dispatcher.requests[0].scene_key == "portrait"
    assert dispatcher.requests[0].scene_title == "Portrait"
    assert dispatcher.requests[0].scene_order == 0
    assert dispatcher.requests[0].scene_count == 2
