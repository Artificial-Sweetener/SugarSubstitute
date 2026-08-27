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

"""Provide deterministic external boundaries for job-queue contracts."""

from __future__ import annotations


from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Hashable
from pathlib import Path
from typing import TypeVar, cast


from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.support.execution import ManualTaskHandle
from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRunStarted,
    GenerationStartResult,
    PreparedGenerationRequest,
)
from substitute.application.generation.job_queue_service import (
    GenerationJobQueueService,
)
from substitute.application.ports import (
    ComfyQueueSnapshot,
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    OutputImageUpdate,
    ProgressUpdate,
)
from substitute.domain.generation import (
    GenerationJobSnapshot,
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
