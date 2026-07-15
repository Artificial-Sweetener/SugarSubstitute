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

"""Contract tests for Substitute-owned generation queue orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Hashable
from pathlib import Path
from typing import Self, TypeVar, cast

from pytest import MonkeyPatch

from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.execution_testing import ManualTaskHandle
from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRunStarted,
    GenerationStartResult,
    PreparedGenerationRequest,
)
from substitute.application.generation.job_queue_service import (
    GenerationQueueBatchEntry,
    GenerationJobLifecycleEvent,
    GenerationJobQueueService,
    GenerationQueueStateChange,
)
import substitute.application.generation.job_queue_service as queue_module
from substitute.application.ports import (
    ComfyQueueSnapshot,
    CubeExecutionTiming,
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    OutputImageUpdate,
    ProgressUpdate,
)
from substitute.domain.generation import (
    GenerationJobSnapshot,
    GenerationQueueJob,
    OutputRunBucket,
)

_T = TypeVar("_T")


@dataclass
class _CallbackRecorder:
    """Collect callback invocations emitted by wrapped generation callbacks."""

    cleared: list[str] = field(default_factory=list)
    completed: list[ListenerCompleted] = field(default_factory=list)
    run_started: list[GenerationRunStarted] = field(default_factory=list)
    failures: list[GenerationFailure] = field(default_factory=list)
    outputs: list[OutputImageUpdate] = field(default_factory=list)
    progress: list[ProgressUpdate] = field(default_factory=list)
    timing: list[GenerationExecutionTiming] = field(default_factory=list)


class _FakeDispatcher:
    """Record prepared dispatch requests and expose listener callbacks to tests."""

    def __init__(
        self,
        *,
        start_results: list[GenerationStartResult] | None = None,
        interrupt_result: InterruptResult | None = None,
    ) -> None:
        """Initialize deterministic dispatch and interrupt outcomes."""

        self.start_results = list(start_results or [])
        self.interrupt_result = interrupt_result or InterruptResult(
            status="sent",
            status_code=200,
            error=None,
        )
        self.requests: list[PreparedGenerationRequest] = []
        self.callbacks: list[GenerationCallbacks] = []
        self.interrupt_calls = 0

    def run_prepared_generation(
        self,
        *,
        request: PreparedGenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Record the request and return the configured start result."""

        self.requests.append(request)
        self.callbacks.append(callbacks)
        if self.start_results:
            result = self.start_results.pop(0)
        else:
            result = GenerationStartResult(
                started=True,
                prompt_id=f"pid-{len(self.requests)}",
                failure=None,
                generation_run_id=f"run-{len(self.requests)}",
                client_id=f"client-{len(self.requests)}",
            )
        if not result.started and result.failure is not None:
            callbacks.on_failure(result.failure)
        return result

    def interrupt_generation(self) -> InterruptResult:
        """Record active cancellation interrupt requests."""

        self.interrupt_calls += 1
        return self.interrupt_result


class _ReconcilingDispatcher(_FakeDispatcher):
    """Fake dispatcher exposing Comfy queue reconciliation state."""

    def __init__(self) -> None:
        """Initialize reconciliation call capture."""

        super().__init__()
        self.get_queue_calls = 0

    def get_comfy_queue_snapshot(self) -> ComfyQueueSnapshot:
        """Return deterministic external Comfy queue state."""

        self.get_queue_calls += 1
        return ComfyQueueSnapshot(
            running_prompt_ids=("external-running",),
            pending_prompt_ids=("external-pending",),
        )


class _BucketResolver:
    """Resolve deterministic output buckets for queue service tests."""

    def __init__(
        self,
        buckets: dict[str, OutputRunBucket] | None = None,
        default: OutputRunBucket | None = None,
    ) -> None:
        """Store workflow-name buckets and a fallback bucket."""

        self.buckets = buckets or {}
        self.default = default or _bucket("2026-04-22")
        self.calls: list[dict[str, object]] = []

    def resolve_run_bucket(
        self,
        *,
        workflow_name: str,
        job_started_at: datetime,
        seed: str = "",
    ) -> OutputRunBucket:
        """Return the configured bucket for one workflow name."""

        self.calls.append(
            {
                "workflow_name": workflow_name,
                "job_started_at": job_started_at,
                "seed": seed,
            }
        )
        return self.buckets.get(workflow_name, self.default)


class _ProjectionKeyProvider:
    """Expose a mutable projection dependency key for queue cache tests."""

    def __init__(self, key: Hashable = "initial") -> None:
        """Store the current key and all timestamps used to build it."""

        self.key = key
        self.calls: list[datetime] = []

    def output_run_projection_cache_key(self, *, now: datetime) -> Hashable:
        """Return the current projection key while recording the timestamp."""

        self.calls.append(now)
        return self.key


class _AllocatorRecorder:
    """Allocate deterministic output run numbers for queue service tests."""

    def __init__(self, numbers: list[int] | None = None, *, fail: bool = False) -> None:
        """Initialize allocation results and call recording."""

        self.numbers = list(numbers or [])
        self.failures_remaining = 1_000_000 if fail else 0
        self.calls: list[dict[str, object]] = []

    def allocate_output_run_number(
        self,
        *,
        bucket: OutputRunBucket,
    ) -> int:
        """Record one allocation request and return the configured base number."""

        self.calls.append({"bucket": bucket})
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise RuntimeError("reservation failed")
        if self.numbers:
            return self.numbers[0]
        return 1


class _CapturingSubmitter:
    """Capture submitted dispatch work without running it automatically."""

    def __init__(self) -> None:
        """Initialize empty submission storage."""

        self.requests: list[TaskRequest[object]] = []
        self.handles: list[ManualTaskHandle[object]] = []
        self.cancellations: list[CancellationToken] = []

    def submit(
        self,
        request: TaskRequest[_T],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[_T]:
        """Store one request for explicit test execution."""

        handle: ManualTaskHandle[_T] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[object], request))
        self.handles.append(cast(ManualTaskHandle[object], handle))
        self.cancellations.append(cancellation)
        return handle


def _callbacks(recorder: _CallbackRecorder | None = None) -> GenerationCallbacks:
    """Build queue-compatible callbacks with deterministic recording."""

    sink = recorder or _CallbackRecorder()
    return GenerationCallbacks(
        clear_output=lambda workflow_id: sink.cleared.append(workflow_id),
        on_run_started=lambda event: sink.run_started.append(event),
        on_progress=lambda event: sink.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda event: sink.outputs.append(event),
        on_failure=lambda failure: sink.failures.append(failure),
        on_timing=lambda event: sink.timing.append(event),
        on_completed=lambda event: sink.completed.append(event),
    )


def _snapshot(
    name: str = "Workflow",
    *,
    positive_prompt_preview: str | None = None,
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> GenerationJobSnapshot:
    """Return one immutable queued workflow snapshot."""

    return GenerationJobSnapshot(
        workflow_id=f"wf-{name.lower()}",
        workflow_name=name,
        sugar_script_text=f'use "cube" as {name}',
        positive_prompt_preview=positive_prompt_preview,
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _bucket(label: str) -> OutputRunBucket:
    """Return one deterministic output run bucket for queue tests."""

    directory = Path("E:/projects") / label
    return OutputRunBucket(
        key=str(directory).replace("\\", "/").casefold(),
        directory=directory,
        display_label=label,
    )


def _completed(workflow_id: str) -> ListenerCompleted:
    """Return one listener completion event for queue callback tests."""

    return ListenerCompleted(
        workflow_id=workflow_id,
        generation_run_id=f"run-{workflow_id}",
        prompt_id=f"pid-{workflow_id}",
    )


def _progress_update(
    *,
    workflow_name: str = "Progress",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    workflow_percent: float | None,
    sampler_percent: float | None,
) -> ProgressUpdate:
    """Return one identity-bearing progress event for a queued workflow."""

    return ProgressUpdate(
        workflow_id=f"wf-{workflow_name.lower()}",
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
    )


def _service(dispatcher: _FakeDispatcher) -> GenerationJobQueueService:
    """Build a queue service with deterministic job ids and timestamps."""

    ids = iter(["job-1", "job-2", "job-3", "job-4"])
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
    )


def _service_with_ids(
    dispatcher: _FakeDispatcher,
    ids: list[str],
    *,
    terminal_history_limit: int = 100,
) -> GenerationJobQueueService:
    """Build a queue service with explicit ids and terminal retention."""

    id_iter = iter(ids)
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(id_iter),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        terminal_history_limit=terminal_history_limit,
    )


def _service_with_allocator(
    dispatcher: _FakeDispatcher,
    allocator: _AllocatorRecorder,
    bucket_resolver: _BucketResolver | None = None,
    projection_key_provider: _ProjectionKeyProvider | None = None,
) -> GenerationJobQueueService:
    """Build a queue service with output run-number reservation enabled."""

    ids = iter(["job-1", "job-2", "job-3", "job-4"])
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        output_run_number_allocator=allocator,
        output_root=Path("E:/projects"),
        output_run_bucket_resolver=bucket_resolver or _BucketResolver(),
        output_run_projection_cache_key_provider=projection_key_provider,
    )


def _service_with_allocator_ids(
    dispatcher: _FakeDispatcher,
    allocator: _AllocatorRecorder,
    ids: list[str],
    bucket_resolver: _BucketResolver | None = None,
    projection_key_provider: _ProjectionKeyProvider | None = None,
) -> GenerationJobQueueService:
    """Build a run-number-aware queue service with explicit deterministic ids."""

    id_iter = iter(ids)
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(id_iter),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        output_run_number_allocator=allocator,
        output_root=Path("E:/projects"),
        output_run_bucket_resolver=bucket_resolver or _BucketResolver(),
        output_run_projection_cache_key_provider=projection_key_provider,
    )


def _owner_scheduled_service(
    dispatcher: _FakeDispatcher,
    scheduled: list[Callable[[], None]],
) -> GenerationJobQueueService:
    """Build a queue service whose initial dispatch scheduling is externally flushed."""

    ids = iter(["job-1", "job-2", "job-3", "job-4"])
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        owner_thread_scheduler=scheduled.append,
    )


def _scheduled_service(
    dispatcher: _FakeDispatcher,
    scheduled: list[object],
) -> GenerationJobQueueService:
    """Build a queue service whose listener transitions are externally flushed."""

    ids = iter(["job-1", "job-2", "job-3", "job-4"])
    return GenerationJobQueueService(
        dispatcher,
        job_id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 4, 22, tzinfo=timezone.utc),
        transition_scheduler=scheduled.append,
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


def test_dispatch_commits_output_run_number_before_start() -> None:
    """Dispatch should commit the output number before calling the dispatcher."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7])
    service = _service_with_allocator(dispatcher, allocator)

    job = service.enqueue_snapshot(_snapshot(), _callbacks())

    assert job.output_run_number == 7
    assert service.jobs()[0].output_run_number == 7
    assert service.jobs()[0].projected_output_run_number is None
    assert dispatcher.requests[0].output_run_number == 7
    assert dispatcher.requests[0].output_job_started_at == datetime(
        2026, 4, 22, tzinfo=timezone.utc
    )
    assert allocator.calls == [{"bucket": _bucket("2026-04-22")}]


def test_pending_jobs_project_distinct_output_numbers_before_outputs_save() -> None:
    """Pending jobs should project distinct future output numbers."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7, 8, 9])
    service = _service_with_allocator(dispatcher, allocator)

    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())
    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())
    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())

    assert [job.output_run_number for job in service.jobs()] == [7, None, None]
    assert [job.projected_output_run_number for job in service.jobs()] == [
        None,
        8,
        9,
    ]
    assert [request.output_run_number for request in dispatcher.requests] == [7]


def test_batch_enqueue_matches_one_at_a_time_output_projection() -> None:
    """Batch enqueue should preserve current projected output-number semantics."""

    snapshots = (
        _snapshot("Workflow"),
        _snapshot("Workflow"),
        _snapshot("Workflow"),
    )
    one_at_a_time_dispatcher = _FakeDispatcher()
    one_at_a_time_service = _service_with_allocator_ids(
        one_at_a_time_dispatcher,
        _AllocatorRecorder([7]),
        ["job-1", "job-2", "job-3"],
    )
    batch_dispatcher = _FakeDispatcher()
    batch_service = _service_with_allocator_ids(
        batch_dispatcher,
        _AllocatorRecorder([7]),
        ["job-1", "job-2", "job-3"],
    )

    for snapshot in snapshots:
        one_at_a_time_service.enqueue_snapshot(snapshot, _callbacks())
    batch_service.enqueue_snapshots(snapshots, _callbacks())

    def output_projection_signature(
        jobs: tuple[GenerationQueueJob, ...],
    ) -> list[tuple[str, str, int | None, int | None, str | None]]:
        """Return fields that define visible output numbering semantics."""

        return [
            (
                job.job_id,
                job.status,
                job.output_run_number,
                job.projected_output_run_number,
                job.projected_output_bucket_label,
            )
            for job in jobs
        ]

    assert output_projection_signature(batch_service.jobs()) == (
        output_projection_signature(one_at_a_time_service.jobs())
    )
    assert [request.output_run_number for request in batch_dispatcher.requests] == [
        request.output_run_number for request in one_at_a_time_dispatcher.requests
    ]


def test_pending_jobs_in_different_buckets_can_project_same_output_number() -> None:
    """Run numbers should be scoped to the resolved output bucket."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=_BucketResolver(
            {
                "Today": _bucket("2026-05-12"),
                "Yesterday": _bucket("2026-05-11"),
            }
        ),
    )

    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())

    jobs = service.jobs()
    assert jobs[0].output_run_number == 1
    assert jobs[0].output_bucket_label == "2026-05-12"
    assert jobs[1].projected_output_run_number == 1
    assert jobs[1].projected_output_bucket_label == "2026-05-11"


def test_jobs_projection_is_cached_until_queue_or_output_dependency_changes() -> None:
    """Repeated queue reads should reuse pending projection until inputs change."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    allocator.calls.clear()
    bucket_resolver.calls.clear()

    first_projection = service.jobs()
    second_projection = service.jobs()

    assert first_projection == second_projection
    assert [job.projected_output_bucket_label for job in first_projection] == [
        None,
        "2026-05-11",
    ]
    assert len(allocator.calls) == 1
    assert [call["workflow_name"] for call in bucket_resolver.calls] == ["Yesterday"]

    projection_key_provider.key = "day-2"
    service.jobs()

    assert len(allocator.calls) == 2
    assert [call["workflow_name"] for call in bucket_resolver.calls] == [
        "Yesterday",
        "Yesterday",
    ]


def test_move_pending_job_invalidates_cached_projection_order() -> None:
    """Moving a pending job should make the next cached queue view reflect order."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(dispatcher, allocator)
    service.enqueue_snapshot(_snapshot("Running"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "Running",
        "Second",
        "Third",
    ]

    service.move_pending_job("job-3", 0)

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "Running",
        "Third",
        "Second",
    ]


def test_progress_update_publishes_progress_event_without_projection_rebuild() -> None:
    """Progress should patch queue state without recomputing pending projection."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.jobs()
    allocator.calls.clear()
    bucket_resolver.calls.clear()
    events: list[GenerationQueueStateChange] = []
    service.add_observer(events.append)
    events.clear()

    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="Today",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )

    assert len(events) == 1
    assert events[0].change_kind == "progress"
    assert events[0].changed_job_id == "job-1"
    assert [job.progress_percent for job in events[0].jobs] == [42.0, None]
    assert allocator.calls == []
    assert bucket_resolver.calls == []


def test_rejected_progress_does_not_recompute_projection() -> None:
    """Rejected stale progress should not invalidate cached queue projection."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.jobs()
    allocator.calls.clear()
    bucket_resolver.calls.clear()
    service.cancel_all_jobs()

    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="Today",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )
    service.jobs()

    assert allocator.calls == []
    assert bucket_resolver.calls == []


def test_duplicate_visible_output_numbers_still_cancel_by_job_id() -> None:
    """Queue actions should use hidden job ids when visible run labels match."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=_BucketResolver(
            {
                "Today": _bucket("2026-05-12"),
                "Yesterday": _bucket("2026-05-11"),
            }
        ),
    )

    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    pending = service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.cancel_job(pending.job_id)

    jobs = service.jobs()
    assert [(job.job_id, job.status) for job in jobs] == [
        ("job-1", "running"),
        ("job-2", "cancelled"),
    ]
    assert jobs[0].output_run_number == 1
    assert jobs[1].output_run_number is None
    assert dispatcher.requests == [
        PreparedGenerationRequest(
            workflow_id="wf-today",
            workflow_name="Today",
            sugar_script_text='use "cube" as Today',
            output_run_number=1,
            output_job_started_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )
    ]


def test_new_pending_jobs_append_to_dispatch_order() -> None:
    """New queued work should enter the back of pending dispatch order."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "First",
        "Second",
        "Third",
    ]
    assert [job.status for job in service.jobs()] == ["running", "pending", "pending"]


def test_dispatch_fails_closed_when_output_run_number_allocation_fails() -> None:
    """Allocation failure should report failure and avoid dispatching the job."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder(fail=True)
    service = _service_with_allocator(dispatcher, allocator)
    recorder = _CallbackRecorder()

    job = service.enqueue_snapshot(_snapshot(), _callbacks(recorder))

    assert job.status == "failed"
    assert "Failed to allocate output run number" in (job.failure_message or "")
    assert [queued_job.status for queued_job in service.jobs()] == ["failed"]
    assert dispatcher.requests == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "queue"


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
        clear_output=callbacks.clear_output,
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


def test_scene_run_jobs_clear_output_once_across_scene_visuals() -> None:
    """Scene jobs sharing one run should not clear each other's accumulated output."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()

    service.enqueue_snapshot(
        _snapshot(
            "First",
            scene_run_id="run-1",
            scene_key="first",
            scene_title="First",
            scene_order=0,
            scene_count=2,
        ),
        _callbacks(recorder),
    )
    service.enqueue_snapshot(
        _snapshot(
            "Second",
            scene_run_id="run-1",
            scene_key="second",
            scene_title="Second",
            scene_order=1,
            scene_count=2,
        ),
        _callbacks(recorder),
    )

    dispatcher.callbacks[0].clear_output("wf-first")
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    dispatcher.callbacks[1].clear_output("wf-second")

    assert recorder.cleared == ["wf-first"]


def test_normal_queued_jobs_keep_per_job_clear_behavior() -> None:
    """Non-scene jobs should retain existing clear-on-first-visual semantics."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)
    recorder = _CallbackRecorder()

    service.enqueue_snapshot(_snapshot("First"), _callbacks(recorder))
    service.enqueue_snapshot(_snapshot("Second"), _callbacks(recorder))

    dispatcher.callbacks[0].clear_output("wf-first")
    assert dispatcher.callbacks[0].on_completed is not None
    dispatcher.callbacks[0].on_completed(_completed("wf-first"))
    dispatcher.callbacks[1].clear_output("wf-second")

    assert recorder.cleared == ["wf-first", "wf-second"]


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


def test_dispatch_reconciles_with_comfy_queue_when_available() -> None:
    """Queue dispatch should inspect Comfy queue state for external work logging."""

    dispatcher = _ReconcilingDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot(), _callbacks())

    assert dispatcher.get_queue_calls == 1


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
    assert job.failure_summary == "Missing xformers"
    assert job.failure_detail == "ModuleNotFoundError: No module named 'xformers'"


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
