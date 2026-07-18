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

"""Own Substitute generation queue ordering, cancellation, and dispatch."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from substitute.application.execution import (
    ExecutionContext,
    TaskScope,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskSubmitter,
)
from substitute.application.generation.failure_summary import (
    summarize_generation_failure,
)
from substitute.application.generation.generation_models import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRunStarted,
    GenerationStartResult,
    PreparedGenerationRequest,
)
from substitute.application.ports.comfy_gateway import (
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.ports.output_run_number_allocator import (
    OutputRunNumberAllocator,
)
from substitute.domain.generation import (
    GenerationCubeExecutionDuration,
    GenerationJobOutputRecord,
    GenerationJobSnapshot,
    GenerationJobStatus,
    GenerationQueueJob,
    OutputRunBucket,
    TERMINAL_GENERATION_JOB_STATUSES,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.generation.job_queue_service")
ACTIVE_GENERATION_JOB_STATUSES = frozenset({"dispatching", "comfy_pending", "running"})
CANCELLABLE_GENERATION_JOB_STATUSES = frozenset(
    {"pending", "dispatching", "comfy_pending", "running"}
)


class PreparedGenerationDispatcher(Protocol):
    """Define prepared generation operations consumed by the queue service."""

    def run_prepared_generation(
        self,
        *,
        request: PreparedGenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Dispatch one prepared generation request."""

    def interrupt_generation(self) -> InterruptResult:
        """Request interruption of active Comfy execution."""


class OutputRunBucketResolver(Protocol):
    """Resolve output buckets for queue projection and dispatch commitment."""

    def resolve_run_bucket(
        self,
        *,
        workflow_name: str,
        job_started_at: datetime,
        seed: str = "",
    ) -> OutputRunBucket:
        """Return the bucket where a queued job will save output files."""


class OutputRunProjectionCacheKeyProvider(Protocol):
    """Provide non-queue dependencies for pending output projection caching."""

    def output_run_projection_cache_key(self, *, now: datetime) -> Hashable:
        """Return a key that changes when pending output projection may change."""


GenerationQueueChangeKind = Literal["structural", "progress"]
QueueObserver = Callable[["GenerationQueueStateChange"], None]
GenerationJobLifecycleAction = Literal[
    "enqueued",
    "dispatching",
    "running",
    "output",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class GenerationJobLifecycleEvent:
    """Describe one queue lifecycle transition with its generation snapshot."""

    action: GenerationJobLifecycleAction
    job: GenerationQueueJob


@dataclass(frozen=True, slots=True)
class GenerationQueueStateChange:
    """Describe one queue publication for UI and action projection."""

    jobs: tuple[GenerationQueueJob, ...]
    change_kind: GenerationQueueChangeKind
    changed_job_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueueProjectionCacheKey:
    """Identify one valid projected queue state."""

    queue_revision: int
    output_projection_key: Hashable


@dataclass(frozen=True, slots=True)
class GenerationQueueBatchEntry:
    """Pair one prepared snapshot with its queue callbacks for batched insertion."""

    snapshot: GenerationJobSnapshot
    callbacks: GenerationCallbacks


@dataclass(frozen=True, slots=True)
class QueueBatchContext:
    """Describe one queue insertion transaction for logging and diagnostics."""

    snapshot_count: int
    scene_run_id: str | None
    scene_count: int | None
    workflow_id: str | None
    workflow_name: str | None


GenerationJobLifecycleObserver = Callable[[GenerationJobLifecycleEvent], None]


class GenerationJobQueueService:
    """Own queued generation snapshots and sequential dispatch."""

    def __init__(
        self,
        dispatcher: PreparedGenerationDispatcher,
        *,
        job_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
        transition_scheduler: Callable[[Callable[[], None]], None] | None = None,
        dispatch_submitter: TaskSubmitter | None = None,
        close_dispatch_submitter: Callable[[], None] | None = None,
        owner_thread_scheduler: Callable[[Callable[[], None]], None] | None = None,
        terminal_history_limit: int = 100,
        output_run_number_allocator: OutputRunNumberAllocator | None = None,
        output_root: Path | None = None,
        output_run_bucket_resolver: OutputRunBucketResolver | None = None,
        output_run_projection_cache_key_provider: (
            OutputRunProjectionCacheKeyProvider | None
        ) = None,
    ) -> None:
        """Initialize queue state with dispatch and identity dependencies."""

        self._dispatcher = dispatcher
        self._job_id_factory = job_id_factory or (lambda: uuid4().hex)
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._transition_scheduler = transition_scheduler or (
            lambda callback: callback()
        )
        self._dispatch_scope = (
            TaskScope(
                submitter=dispatch_submitter,
                scope_id="generation_queue_dispatch",
            )
            if dispatch_submitter is not None
            else None
        )
        self._close_dispatch_submitter = close_dispatch_submitter or (lambda: None)
        self._owner_thread_scheduler = owner_thread_scheduler or (
            self._transition_scheduler
            if dispatch_submitter is not None
            else (lambda callback: callback())
        )
        self._terminal_history_limit = max(0, terminal_history_limit)
        self._output_run_number_allocator = output_run_number_allocator
        self._output_root = output_root
        self._output_run_bucket_resolver = output_run_bucket_resolver
        self._output_run_projection_cache_key_provider = (
            output_run_projection_cache_key_provider
        )
        self._jobs: list[GenerationQueueJob] = []
        self._queue_projection_revision = 0
        self._projected_jobs_cache: tuple[GenerationQueueJob, ...] | None = None
        self._projected_jobs_cache_key: QueueProjectionCacheKey | None = None
        self._callbacks_by_job_id: dict[str, GenerationCallbacks] = {}
        self._outputs_by_job_id: dict[str, list[GenerationJobOutputRecord]] = {}
        self._reserved_output_numbers_by_bucket: dict[str, set[int]] = {}
        self._observers: list[QueueObserver] = []
        self._lifecycle_observers: list[GenerationJobLifecycleObserver] = []
        self._active_job_id: str | None = None
        self._cleared_scene_run_ids: set[str] = set()
        self._dispatch_tokens_by_job_id: dict[str, str] = {}
        self._dispatch_request_id = 0
        self._is_shutdown = False

    def add_observer(self, observer: QueueObserver) -> None:
        """Register one queue observer and immediately publish current state."""

        self._observers.append(observer)
        observer(
            GenerationQueueStateChange(
                jobs=self.jobs(),
                change_kind="structural",
            )
        )

    def remove_observer(self, observer: QueueObserver) -> None:
        """Unregister one queue observer when a shell surface is disposed."""

        self._observers = [
            registered for registered in self._observers if registered != observer
        ]

    def add_lifecycle_observer(
        self,
        observer: GenerationJobLifecycleObserver,
    ) -> None:
        """Register one observer for detailed queue lifecycle transitions."""

        self._lifecycle_observers.append(observer)

    def remove_lifecycle_observer(
        self,
        observer: GenerationJobLifecycleObserver,
    ) -> None:
        """Unregister one queue lifecycle observer."""

        self._lifecycle_observers = [
            registered
            for registered in self._lifecycle_observers
            if registered != observer
        ]

    def enqueue_snapshot(
        self,
        snapshot: GenerationJobSnapshot,
        callbacks: GenerationCallbacks,
    ) -> GenerationQueueJob:
        """Append one snapshot and dispatch if the queue is idle."""

        jobs = self.enqueue_snapshots((snapshot,), callbacks)
        if not jobs:
            raise RuntimeError("Single snapshot enqueue unexpectedly returned no job.")
        return jobs[0]

    def enqueue_snapshots(
        self,
        snapshots: tuple[GenerationJobSnapshot, ...],
        callbacks: GenerationCallbacks,
    ) -> tuple[GenerationQueueJob, ...]:
        """Append same-callback snapshots as one queue update transaction."""

        return self.enqueue_snapshot_entries(
            tuple(
                GenerationQueueBatchEntry(snapshot=snapshot, callbacks=callbacks)
                for snapshot in snapshots
            )
        )

    def enqueue_snapshot_entries(
        self,
        entries: tuple[GenerationQueueBatchEntry, ...],
    ) -> tuple[GenerationQueueJob, ...]:
        """Append prepared snapshot entries as one queue update transaction."""

        if not entries:
            return ()
        batch_context = self._batch_context_for_entries(entries)
        jobs = tuple(self._create_pending_job(entry.snapshot) for entry in entries)
        for entry, job in zip(entries, jobs, strict=True):
            self._append_pending_job(job, entry.callbacks)
        job_ids = tuple(job.job_id for job in jobs)
        log_info(
            _LOGGER,
            "Enqueued generation job snapshot batch",
            batch_size=batch_context.snapshot_count,
            scene_run_id=batch_context.scene_run_id,
            scene_count=batch_context.scene_count,
            workflow_id=batch_context.workflow_id,
            first_workflow_name=batch_context.workflow_name,
            job_ids=job_ids,
        )
        self._invalidate_projected_jobs()
        self._notify_structural_observers()
        for job in jobs:
            self._notify_lifecycle(job.job_id, "enqueued")
        self._schedule_dispatch_next_if_idle()
        return tuple(self._job_by_id(job.job_id) or job for job in jobs)

    def _create_pending_job(
        self,
        snapshot: GenerationJobSnapshot,
    ) -> GenerationQueueJob:
        """Create one pending queue job without publishing queue changes."""

        job = GenerationQueueJob(
            job_id=self._job_id_factory(),
            snapshot=snapshot,
            created_at=self._clock(),
            status="pending",
        )
        return job

    def _append_pending_job(
        self,
        job: GenerationQueueJob,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Append one pending queue job and store its callback/output state."""

        self._jobs.append(job)
        self._callbacks_by_job_id[job.job_id] = callbacks
        self._outputs_by_job_id[job.job_id] = []

    @staticmethod
    def _batch_context_for_entries(
        entries: tuple[GenerationQueueBatchEntry, ...],
    ) -> QueueBatchContext:
        """Return logging context for one queue insertion transaction."""

        snapshots = tuple(entry.snapshot for entry in entries)
        first_snapshot = snapshots[0]
        first_scene_run_id = first_snapshot.scene_run_id
        scene_run_id = (
            first_scene_run_id
            if first_scene_run_id
            and all(
                snapshot.scene_run_id == first_scene_run_id for snapshot in snapshots
            )
            else None
        )
        first_scene_count = first_snapshot.scene_count
        scene_count = (
            first_scene_count
            if scene_run_id is not None
            and first_scene_count is not None
            and all(snapshot.scene_count == first_scene_count for snapshot in snapshots)
            else None
        )
        return QueueBatchContext(
            snapshot_count=len(snapshots),
            scene_run_id=scene_run_id,
            scene_count=scene_count,
            workflow_id=first_snapshot.workflow_id,
            workflow_name=first_snapshot.workflow_name,
        )

    def cancel_job(self, job_id: str) -> None:
        """Cancel a pending or active job using local or Comfy interruption."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        self._cancel_job(
            job,
            notify=True,
            dispatch_next=True,
            lifecycle_action="cancelled",
        )

    def skip_active_job(self) -> None:
        """Cancel the active queued job and continue with the next pending job."""

        if self._active_job_id is None:
            return
        job = self._job_by_id(self._active_job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            self._active_job_id = None
            self._dispatch_next_if_idle()
            return
        self._cancel_job(
            job,
            notify=True,
            dispatch_next=True,
            lifecycle_action="skipped",
        )

    def cancel_all_jobs(self) -> None:
        """Cancel all queued work without dispatching another pending job."""

        jobs_to_cancel = [
            job
            for job in self._jobs
            if job.status not in TERMINAL_GENERATION_JOB_STATUSES
        ]
        if not jobs_to_cancel:
            return
        for job in jobs_to_cancel:
            self._cancel_job(
                job,
                notify=False,
                dispatch_next=False,
                lifecycle_action="cancelled",
            )
        self._active_job_id = None
        self._notify_structural_observers()

    def _cancel_job(
        self,
        job: GenerationQueueJob,
        *,
        notify: bool,
        dispatch_next: bool,
        lifecycle_action: Literal["skipped", "cancelled"],
    ) -> None:
        """Cancel one non-terminal job with optional observer and dispatch steps."""

        if job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        if job.status == "pending":
            self._replace_job(
                job.job_id,
                status="cancelled",
                completed_at=self._clock(),
            )
            self._callbacks_by_job_id.pop(job.job_id, None)
            self._dispatch_tokens_by_job_id.pop(job.job_id, None)
            self._notify_lifecycle(job.job_id, lifecycle_action)
            log_info(_LOGGER, "Cancelled pending generation job", job_id=job.job_id)
            self._prune_terminal_history()
            if notify:
                self._notify_structural_observers(changed_job_id=job.job_id)
            if dispatch_next:
                self._schedule_dispatch_next_if_idle()
            return

        self._replace_job(
            job.job_id,
            status="cancelled",
            completed_at=self._clock(),
        )
        self._callbacks_by_job_id.pop(job.job_id, None)
        self._dispatch_tokens_by_job_id.pop(job.job_id, None)
        self._notify_lifecycle(job.job_id, lifecycle_action)
        if job.status == "comfy_pending" and job.prompt_id is not None:
            self._delete_pending_comfy_prompt(job)
        else:
            self._interrupt_active_comfy_prompt(job.job_id)
        if self._active_job_id == job.job_id:
            self._active_job_id = None
        self._prune_terminal_history()
        if notify:
            self._notify_structural_observers(changed_job_id=job.job_id)
        if dispatch_next:
            self._schedule_dispatch_next_if_idle()

    def remove_terminal_job(self, job_id: str) -> None:
        """Remove a completed, failed, or cancelled job from the visible queue."""

        job = self._job_by_id(job_id)
        if job is None or job.status not in TERMINAL_GENERATION_JOB_STATUSES:
            return
        index = self._index_by_id(job_id)
        if index is None:
            return
        self._callbacks_by_job_id.pop(job_id, None)
        self._outputs_by_job_id.pop(job_id, None)
        del self._jobs[index]
        log_info(
            _LOGGER,
            "Removed terminal generation queue job",
            job_id=job_id,
            status=job.status,
        )
        self._invalidate_projected_jobs()
        self._notify_structural_observers(changed_job_id=job_id)

    def move_pending_job(self, job_id: str, target_index: int) -> None:
        """Move one pending job to a new pending-job index."""

        source_index = self._index_by_id(job_id)
        if source_index is None:
            return
        job = self._jobs[source_index]
        if job.status != "pending":
            return

        pending_jobs = [
            candidate for candidate in self._jobs if candidate.status == "pending"
        ]
        pending_ids = [candidate.job_id for candidate in pending_jobs]
        old_pending_index = pending_ids.index(job_id)
        bounded_target = max(0, min(target_index, len(pending_jobs) - 1))
        if old_pending_index == bounded_target:
            return

        pending_ids.pop(old_pending_index)
        pending_ids.insert(bounded_target, job_id)
        pending_order = iter(pending_ids)
        pending_by_id = {
            candidate.job_id: candidate
            for candidate in self._jobs
            if candidate.status == "pending"
        }
        self._jobs = [
            pending_by_id[next(pending_order)]
            if candidate.status == "pending"
            else candidate
            for candidate in self._jobs
        ]
        self._invalidate_projected_jobs()
        self._notify_structural_observers(changed_job_id=job_id)

    def jobs(self) -> tuple[GenerationQueueJob, ...]:
        """Return the current ordered queue view."""

        return self._projected_jobs()

    def _projected_jobs(self) -> tuple[GenerationQueueJob, ...]:
        """Return cached projected jobs, rebuilding only when inputs change."""

        projection_now = self._clock()
        cache_key = self._current_projection_cache_key(projection_now)
        if (
            self._projected_jobs_cache is not None
            and self._projected_jobs_cache_key == cache_key
        ):
            return self._projected_jobs_cache
        projected_jobs = self._jobs_with_projected_output_numbers(projection_now)
        self._projected_jobs_cache = projected_jobs
        self._projected_jobs_cache_key = cache_key
        return projected_jobs

    def _current_projection_cache_key(
        self,
        projection_now: datetime,
    ) -> QueueProjectionCacheKey:
        """Return the dependency key for the current projected queue view."""

        output_projection_key = self._output_run_projection_cache_key(projection_now)
        return QueueProjectionCacheKey(
            queue_revision=self._queue_projection_revision,
            output_projection_key=output_projection_key,
        )

    def _output_run_projection_cache_key(
        self,
        projection_now: datetime,
    ) -> Hashable:
        """Return output dependencies that can affect pending projection."""

        if self._output_run_projection_cache_key_provider is None:
            return (
                None
                if self._output_root is None
                else str(Path(self._output_root).resolve())
                .replace("\\", "/")
                .casefold()
            )
        return self._output_run_projection_cache_key_provider.output_run_projection_cache_key(
            now=projection_now
        )

    def _invalidate_projected_jobs(self) -> None:
        """Mark transient queue projection stale after a structural change."""

        self._queue_projection_revision += 1
        self._projected_jobs_cache = None
        self._projected_jobs_cache_key = None
        pass

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Return the latest known cube duration for one workflow output source."""

        for job in reversed(self._jobs):
            if job.snapshot.workflow_id != workflow_id:
                continue
            for duration in job.cube_execution_durations:
                if source_key and duration.source_key == source_key:
                    return duration.duration_ms
            for duration in job.cube_execution_durations:
                if cube_alias and duration.cube_alias == cube_alias:
                    return duration.duration_ms
        return None

    def _jobs_with_projected_output_numbers(
        self,
        projection_now: datetime,
    ) -> tuple[GenerationQueueJob, ...]:
        """Return queue jobs with transient pending output number projections."""

        next_number_by_bucket_key: dict[str, int] = {}
        projected_jobs: list[GenerationQueueJob] = []
        for job in self._jobs:
            if job.output_run_number is not None and job.output_bucket_key is not None:
                next_number_by_bucket_key[job.output_bucket_key] = max(
                    next_number_by_bucket_key.get(job.output_bucket_key, 1),
                    job.output_run_number + 1,
                )
            if job.status != "pending":
                projected_jobs.append(
                    replace(
                        job,
                        projected_output_run_number=None,
                        projected_output_bucket_key=None,
                        projected_output_bucket_directory=None,
                        projected_output_bucket_label=None,
                    ),
                )
                continue
            bucket = self._resolve_output_run_bucket(
                workflow_name=job.snapshot.workflow_name,
                job_started_at=projection_now,
                log_context=None,
            )
            if bucket is None:
                projected_jobs.append(
                    replace(
                        job,
                        projected_output_run_number=None,
                        projected_output_bucket_key=None,
                        projected_output_bucket_directory=None,
                        projected_output_bucket_label=None,
                    ),
                )
                continue
            projected_number = next_number_by_bucket_key.get(bucket.key)
            if projected_number is None:
                projected_number = self._next_output_run_number_for_bucket(
                    bucket=bucket,
                    log_context=None,
                    allow_committed_fallback=True,
                )
            if projected_number is None:
                projected_jobs.append(
                    replace(
                        job,
                        projected_output_run_number=None,
                        projected_output_bucket_key=bucket.key,
                        projected_output_bucket_directory=bucket.directory,
                        projected_output_bucket_label=bucket.display_label,
                    ),
                )
                continue
            projected_jobs.append(
                replace(
                    job,
                    projected_output_run_number=projected_number,
                    projected_output_bucket_key=bucket.key,
                    projected_output_bucket_directory=bucket.directory,
                    projected_output_bucket_label=bucket.display_label,
                ),
            )
            next_number_by_bucket_key[bucket.key] = projected_number + 1
        return tuple(projected_jobs)

    def snapshot_for_job(self, job_id: str) -> GenerationJobSnapshot | None:
        """Return the queued Sugar snapshot for one visible job."""

        job = self._job_by_id(job_id)
        if job is None:
            return None
        return job.snapshot

    def job_for_result_replay(self, job_id: str) -> GenerationQueueJob | None:
        """Return one visible live job for current-session result replay."""

        return self._job_by_id(job_id)

    def output_records_for_job(
        self,
        job_id: str,
    ) -> tuple[GenerationJobOutputRecord, ...]:
        """Return current-session output records for one visible queue job."""

        if self._job_by_id(job_id) is None:
            return ()
        return tuple(self._outputs_by_job_id.get(job_id, ()))

    def has_active_job(self) -> bool:
        """Return whether the queue currently owns active cancellable work."""

        if self._active_job_id is None:
            return False
        job = self._job_by_id(self._active_job_id)
        return job is not None and job.status in ACTIVE_GENERATION_JOB_STATUSES

    def has_cancellable_jobs(self) -> bool:
        """Return whether any queued job can be cancelled."""

        return any(
            job.status in CANCELLABLE_GENERATION_JOB_STATUSES for job in self._jobs
        )

    def shutdown(self) -> None:
        """Cancel dispatch execution and release the owned dispatch route."""

        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._dispatch_tokens_by_job_id.clear()
        if self._dispatch_scope is not None:
            self._dispatch_scope.close(reason="generation_queue_shutdown")
        self._close_dispatch_submitter()

    def _commit_output_run_number(
        self,
        job: GenerationQueueJob,
        callbacks: GenerationCallbacks,
    ) -> GenerationQueueJob | None:
        """Commit the saved-file number for one job about to dispatch."""

        if self._output_run_number_allocator is None:
            return job
        job_started_at = self._clock()
        bucket = self._resolve_output_run_bucket(
            workflow_name=job.snapshot.workflow_name,
            job_started_at=job_started_at,
            log_context=job,
        )
        if bucket is None:
            self._fail_output_run_number_commit(job, callbacks)
            return None
        output_run_number = self._next_output_run_number_for_bucket(
            bucket=bucket,
            log_context=job,
            allow_committed_fallback=False,
        )
        if output_run_number is None:
            self._fail_output_run_number_commit(job, callbacks)
            return None
        self._replace_job(
            job.job_id,
            output_run_number=output_run_number,
            output_bucket_key=bucket.key,
            output_bucket_directory=bucket.directory,
            output_bucket_label=bucket.display_label,
            started_at=job_started_at,
        )
        self._reserve_output_run_number(
            bucket_key=bucket.key,
            output_run_number=output_run_number,
        )
        return self._job_by_id(job.job_id)

    def _next_output_run_number_for_bucket(
        self,
        *,
        bucket: OutputRunBucket,
        log_context: GenerationQueueJob | None,
        allow_committed_fallback: bool,
    ) -> int | None:
        """Return the next committed output number for an output bucket."""

        committed_floor = self._next_in_memory_reserved_output_run_number(
            bucket.key,
        )
        if self._output_run_number_allocator is None:
            return committed_floor
        try:
            allocated_number = (
                self._output_run_number_allocator.allocate_output_run_number(
                    bucket=bucket,
                )
            )
        except Exception as error:
            if log_context is not None:
                log_exception(
                    _LOGGER,
                    "Failed to allocate output run number for generation job",
                    job_id=log_context.job_id,
                    workflow_id=log_context.snapshot.workflow_id,
                    workflow_name=log_context.snapshot.workflow_name,
                    output_bucket_key=bucket.key,
                    output_bucket_directory=str(bucket.directory),
                    error=error,
                )
            return committed_floor if allow_committed_fallback else None
        if committed_floor is None:
            return allocated_number
        return max(allocated_number, committed_floor)

    def _next_in_memory_reserved_output_run_number(
        self,
        bucket_key: str,
    ) -> int | None:
        """Return the next output number after current-session reservations."""

        reserved_numbers = self._reserved_output_numbers_by_bucket.get(bucket_key)
        if not reserved_numbers:
            return None
        return max(reserved_numbers) + 1

    def _reserve_output_run_number(
        self,
        *,
        bucket_key: str,
        output_run_number: int,
    ) -> None:
        """Remember one committed run number for this process lifetime."""

        reserved_numbers = self._reserved_output_numbers_by_bucket.setdefault(
            bucket_key,
            set(),
        )
        reserved_numbers.add(output_run_number)

    def _resolve_output_run_bucket(
        self,
        *,
        workflow_name: str,
        job_started_at: datetime,
        log_context: GenerationQueueJob | None,
    ) -> OutputRunBucket | None:
        """Resolve the output bucket for queue-visible run numbering."""

        if self._output_run_bucket_resolver is not None:
            try:
                return self._output_run_bucket_resolver.resolve_run_bucket(
                    workflow_name=workflow_name,
                    job_started_at=job_started_at,
                )
            except Exception as error:
                if log_context is not None:
                    log_exception(
                        _LOGGER,
                        "Failed to resolve output run bucket for generation job",
                        job_id=log_context.job_id,
                        workflow_id=log_context.snapshot.workflow_id,
                        workflow_name=workflow_name,
                        error=error,
                    )
                return None
        if self._output_root is None:
            if log_context is not None:
                log_warning(
                    _LOGGER,
                    "Output run bucket resolver configured without output root",
                    job_id=log_context.job_id,
                    workflow_id=log_context.snapshot.workflow_id,
                    workflow_name=workflow_name,
                )
            return None
        directory = Path(self._output_root).resolve()
        return OutputRunBucket(
            key=str(directory).replace("\\", "/").casefold(),
            directory=directory,
            display_label=directory.name or str(directory),
        )

    def _fail_output_run_number_commit(
        self,
        job: GenerationQueueJob,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Fail one job that cannot receive a committed output number."""

        message = "Failed to allocate output run number."
        callbacks.on_failure(
            GenerationFailure(
                stage="queue",
                workflow_id=job.snapshot.workflow_id,
                message=message,
            )
        )
        self._mark_failed(job.job_id, message)

    def _schedule_dispatch_next_if_idle(self) -> None:
        """Schedule queue dispatch on the owner thread."""

        self._owner_thread_scheduler(self._dispatch_next_if_idle)

    def _dispatch_next_if_idle(self) -> None:
        """Dispatch the first pending job when no active job is running."""

        if self._is_shutdown:
            return
        if self._active_job_id is not None:
            return
        next_job = next(
            (candidate for candidate in self._jobs if candidate.status == "pending"),
            None,
        )
        if next_job is None:
            return

        self._log_unexpected_external_comfy_work()
        callbacks = self._callbacks_by_job_id.get(next_job.job_id)
        if callbacks is None:
            self._replace_job(next_job.job_id, status="cancelled")
            self._notify_structural_observers(changed_job_id=next_job.job_id)
            self._dispatch_next_if_idle()
            return

        committed_job = self._commit_output_run_number(next_job, callbacks)
        if committed_job is None:
            return

        self._active_job_id = committed_job.job_id
        job_started_at = committed_job.started_at or self._clock()
        self._replace_job(
            committed_job.job_id,
            status="dispatching",
            started_at=job_started_at,
        )
        self._notify_structural_observers(changed_job_id=committed_job.job_id)
        self._notify_lifecycle(committed_job.job_id, "dispatching")
        request = PreparedGenerationRequest(
            workflow_id=committed_job.snapshot.workflow_id,
            workflow_name=committed_job.snapshot.workflow_name,
            sugar_script_text=committed_job.snapshot.sugar_script_text,
            direct_workflow_plan=committed_job.snapshot.direct_workflow_plan,
            output_run_number=committed_job.output_run_number,
            output_job_started_at=job_started_at,
            scene_run_id=committed_job.snapshot.scene_run_id,
            scene_key=committed_job.snapshot.scene_key,
            scene_title=committed_job.snapshot.scene_title,
            scene_order=committed_job.snapshot.scene_order,
            scene_count=committed_job.snapshot.scene_count,
        )
        wrapped_callbacks = self._wrap_callbacks(committed_job.job_id, callbacks)
        if self._dispatch_scope is not None:
            committed_job_id = committed_job.job_id
            token = uuid4().hex
            self._dispatch_tokens_by_job_id[committed_job_id] = token
            self._dispatch_request_id += 1
            dispatch_request: TaskRequest[GenerationStartResult] = TaskRequest(
                identity=TaskIdentity(
                    request_id=self._dispatch_request_id,
                    domain="generation_dispatch",
                    parts=(
                        ("job_id", committed_job_id),
                        ("workflow_id", committed_job.snapshot.workflow_id),
                    ),
                ),
                context=ExecutionContext(
                    operation="generation_dispatch",
                    reason="queued_generation_job",
                    lane="generation_dispatch",
                    safe_fields=(
                        ("request_id", self._dispatch_request_id),
                        ("job_id", committed_job_id),
                        ("workflow_id", committed_job.snapshot.workflow_id),
                    ),
                ),
                work=lambda _token: self._run_dispatch_task(
                    request,
                    wrapped_callbacks,
                ),
            )
            handle = self._dispatch_scope.submit(dispatch_request)

            def schedule_dispatch_completion(
                outcome: TaskOutcome[GenerationStartResult],
                *,
                job_id: str = committed_job_id,
                dispatch_token: str = token,
            ) -> None:
                """Apply dispatch-task completion through the execution dispatcher."""

                self._handle_dispatch_task_completed(
                    job_id,
                    dispatch_token,
                    outcome,
                )

            handle.add_done_callback(
                schedule_dispatch_completion,
                reason="generation_dispatch_completed",
            )
            return
        result = self._dispatcher.run_prepared_generation(
            request=request,
            callbacks=wrapped_callbacks,
        )
        self._handle_dispatch_result(
            committed_job.job_id,
            result,
        )

    def _run_dispatch_task(
        self,
        request: PreparedGenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Run blocking generation dispatch through the execution lane."""

        return self._dispatcher.run_prepared_generation(
            request=request,
            callbacks=callbacks,
        )

    def _handle_dispatch_task_completed(
        self,
        job_id: str,
        dispatch_token: str,
        outcome: TaskOutcome[GenerationStartResult],
    ) -> None:
        """Apply a dispatch-task result on the owner thread."""

        if self._dispatch_tokens_by_job_id.get(job_id) != dispatch_token:
            return
        self._dispatch_tokens_by_job_id.pop(job_id, None)
        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        if outcome.status == "cancelled":
            self._mark_failed(
                job_id,
                "Generation dispatch cancelled.",
                detail=outcome.cancellation_reason,
            )
            return
        if outcome.status == "failed":
            error = outcome.error or RuntimeError("Generation dispatch failed.")
            log_exception(
                _LOGGER,
                "Generation dispatch task failed",
                job_id=job_id,
                error=error,
            )
            self._mark_failed(job_id, "Generation dispatch failed.", detail=str(error))
            return
        result = outcome.result
        if result is None:
            self._mark_failed(
                job_id,
                "Generation dispatch failed.",
                detail="Generation dispatch returned no result.",
            )
            return
        self._handle_dispatch_result(job_id, result)

    def _handle_dispatch_result(
        self,
        job_id: str,
        result: GenerationStartResult,
    ) -> None:
        """Move a dispatching job to running or failed from a start result."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        if not result.started:
            failure_message = (
                result.failure.message
                if result.failure is not None
                else "Generation dispatch failed."
            )
            self._mark_failed(
                job_id,
                failure_message,
                detail=result.failure.detail if result.failure is not None else None,
            )
            return
        self._replace_job(
            job_id,
            status="running",
            prompt_id=result.prompt_id,
            generation_run_id=result.generation_run_id,
            client_id=result.client_id,
        )
        self._notify_structural_observers(changed_job_id=job_id)
        self._notify_lifecycle(job_id, "running")

    def _wrap_callbacks(
        self,
        job_id: str,
        callbacks: GenerationCallbacks,
    ) -> GenerationCallbacks:
        """Wrap generation callbacks so queue state follows execution events."""

        def on_output_image(event: OutputImageUpdate) -> None:
            def handle_output() -> None:
                self._handle_generation_output(job_id, event)
                callbacks.on_output_image(event)

            self._transition_scheduler(handle_output)

        def on_progress(event: ProgressUpdate) -> None:
            def handle_progress() -> None:
                if self._handle_generation_progress(job_id, event):
                    callbacks.on_progress(event)

            self._transition_scheduler(handle_progress)

        def on_timing(event: GenerationExecutionTiming) -> None:
            def handle_timing() -> None:
                self._handle_generation_timing(job_id, event)
                callbacks.on_timing(event)

            self._transition_scheduler(handle_timing)

        def on_model_load_progress(event: ModelLoadProgressUpdate) -> None:
            def handle_model_load_progress() -> None:
                callbacks.on_model_load_progress(event)

            self._transition_scheduler(handle_model_load_progress)

        def on_preview(event: PreviewImageUpdate) -> None:
            def handle_preview() -> None:
                callbacks.on_preview(event)

            self._transition_scheduler(handle_preview)

        def on_run_started(event: GenerationRunStarted) -> None:
            def handle_run_started() -> None:
                self._replace_job(
                    job_id,
                    prompt_id=event.prompt_id,
                    generation_run_id=event.generation_run_id,
                    client_id=event.client_id,
                )
                if callbacks.on_run_started is not None:
                    callbacks.on_run_started(event)

            self._transition_scheduler(handle_run_started)

        def on_failure(failure: GenerationFailure) -> None:
            self._transition_scheduler(
                lambda: self._handle_generation_failure_profiled(
                    job_id,
                    failure,
                    callbacks,
                )
            )

        def on_completed(event: ListenerCompleted) -> None:
            self._transition_scheduler(
                lambda: self._handle_generation_completed_profiled(
                    job_id,
                    event,
                    callbacks,
                )
            )

        def clear_output(workflow_id: str) -> None:
            self._transition_scheduler(
                lambda: self._clear_output_for_job_visual_profiled(
                    job_id=job_id,
                    workflow_id=workflow_id,
                    callbacks=callbacks,
                )
            )

        return GenerationCallbacks(
            randomize_seeds=None,
            clear_output=clear_output,
            on_run_started=on_run_started,
            on_progress=on_progress,
            on_model_load_progress=on_model_load_progress,
            on_preview=on_preview,
            on_output_image=on_output_image,
            on_failure=on_failure,
            on_timing=on_timing,
            on_completed=on_completed,
        )

    def _clear_output_for_job_visual_profiled(
        self,
        *,
        job_id: str,
        workflow_id: str,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Clear queued output visual state."""

        self._clear_output_for_job_visual(
            job_id=job_id,
            workflow_id=workflow_id,
            callbacks=callbacks,
        )

    def _clear_output_for_job_visual(
        self,
        *,
        job_id: str,
        workflow_id: str,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Clear output once per scene run or once per normal queued job visual."""

        job = self._job_by_id(job_id)
        if job is None:
            callbacks.clear_output(workflow_id)
            return
        scene_run_id = job.snapshot.scene_run_id
        if scene_run_id is None:
            callbacks.clear_output(workflow_id)
            return
        if scene_run_id in self._cleared_scene_run_ids:
            return
        self._cleared_scene_run_ids.add(scene_run_id)
        callbacks.clear_output(workflow_id)

    def _handle_generation_output(
        self,
        job_id: str,
        event: OutputImageUpdate,
    ) -> None:
        """Record latest output metadata for one queued job."""

        job = self._job_by_id(job_id)
        if job is None:
            return
        self._replace_job(
            job_id,
            last_output_path=event.file_path,
            last_output_node_id=event.node_id,
            output_count=job.output_count + 1,
        )
        self._append_live_output_record(
            job_id=job_id,
            event=event,
            sequence=job.output_count + 1,
        )
        self._notify_structural_observers(changed_job_id=job_id)
        self._notify_lifecycle(job_id, "output")

    def _append_live_output_record(
        self,
        *,
        job_id: str,
        event: OutputImageUpdate,
        sequence: int,
    ) -> None:
        """Retain one output record for current-session queue replay."""

        records = self._outputs_by_job_id.setdefault(job_id, [])
        records.append(
            GenerationJobOutputRecord(
                job_id=job_id,
                output_path=event.file_path,
                node_id=event.node_id,
                created_at=self._clock(),
                sequence=sequence,
                source_key=event.source_key,
                source_label=event.source_label,
                scene_run_id=event.scene_run_id,
                scene_key=event.scene_key,
                scene_title=event.scene_title,
                scene_order=event.scene_order,
                scene_count=event.scene_count,
                node_title=None,
                metadata={
                    "list_index": event.list_index,
                    "batch_index": event.batch_index,
                    "width": event.artifact_width,
                    "height": event.artifact_height,
                },
            )
        )

    def _handle_generation_progress(
        self,
        job_id: str,
        event: ProgressUpdate,
    ) -> bool:
        """Record live workflow progress and return whether it is still valid."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            self._log_rejected_progress(job_id, event, reason="terminal_or_missing_job")
            return False
        if self._active_job_id is not None and self._active_job_id != job_id:
            self._log_rejected_progress(job_id, event, reason="not_active_job")
            return False
        if not _progress_event_matches_job(job, event):
            self._log_rejected_progress(job_id, event, reason="identity_mismatch")
            return False
        if event.workflow_percent is None:
            return True
        progress_percent = max(0.0, min(100.0, event.workflow_percent))
        if job.progress_percent == progress_percent:
            return True
        self._replace_job_progress(job_id, progress_percent=progress_percent)
        self._notify_progress_observers(changed_job_id=job_id)
        return True

    @staticmethod
    def _log_rejected_progress(
        job_id: str,
        event: ProgressUpdate,
        *,
        reason: str,
    ) -> None:
        """Log a stale progress event rejected by queue lifecycle checks."""

        log_debug(
            _LOGGER,
            "Rejected queued generation progress",
            job_id=job_id,
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
            client_id=event.client_id,
            reason=reason,
        )

    def _handle_generation_timing(
        self,
        job_id: str,
        event: GenerationExecutionTiming,
    ) -> None:
        """Record execution timing for one queued job."""

        job = self._job_by_id(job_id)
        if job is None:
            return
        cube_durations = tuple(
            GenerationCubeExecutionDuration(
                cube_alias=timing.cube_alias,
                source_key=timing.source_key,
                duration_ms=timing.duration_ms,
            )
            for timing in event.cube_timings
        )
        if (
            job.execution_duration_ms == event.job_duration_ms
            and job.cube_execution_durations == cube_durations
        ):
            return
        self._replace_job(
            job_id,
            execution_duration_ms=event.job_duration_ms,
            cube_execution_durations=cube_durations,
        )
        self._notify_structural_observers(changed_job_id=job_id)

    def _handle_generation_failure(
        self,
        job_id: str,
        failure: GenerationFailure,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Apply a listener failure transition on the configured queue thread."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        self._mark_failed(job_id, failure.message, detail=failure.detail)
        callbacks.on_failure(failure)

    def _handle_generation_failure_profiled(
        self,
        job_id: str,
        failure: GenerationFailure,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Apply a listener failure transition."""

        self._handle_generation_failure(job_id, failure, callbacks)

    def _handle_generation_completed(
        self,
        job_id: str,
        event: ListenerCompleted,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Apply a listener completion transition on the configured queue thread."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        self._mark_completed(job_id)
        if callbacks.on_completed is not None:
            callbacks.on_completed(event)

    def _handle_generation_completed_profiled(
        self,
        job_id: str,
        event: ListenerCompleted,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Apply a listener completion transition."""

        self._handle_generation_completed(job_id, event, callbacks)

    def _interrupt_active_comfy_prompt(self, job_id: str) -> None:
        """Interrupt Comfy for one active Substitute-owned job."""

        interrupt_result = self._dispatcher.interrupt_generation()
        if interrupt_result.status != "sent":
            log_warning(
                _LOGGER,
                "Active generation job cancellation interrupt failed",
                job_id=job_id,
                interrupt_status=interrupt_result.status,
                status_code=interrupt_result.status_code,
                error=interrupt_result.error,
            )
            return
        log_info(_LOGGER, "Cancelled active generation job", job_id=job_id)

    def _delete_pending_comfy_prompt(self, job: GenerationQueueJob) -> None:
        """Delete one known Comfy-pending prompt when the dispatcher supports it."""

        delete_pending_prompt = getattr(
            self._dispatcher,
            "delete_pending_comfy_prompt",
            None,
        )
        if not callable(delete_pending_prompt):
            self._interrupt_active_comfy_prompt(job.job_id)
            return
        result = delete_pending_prompt(job.prompt_id)
        if result.status != "deleted":
            log_warning(
                _LOGGER,
                "Comfy pending prompt delete failed",
                job_id=job.job_id,
                prompt_id=job.prompt_id,
                status=result.status,
                status_code=result.status_code,
                error=result.error,
            )
            return
        log_info(
            _LOGGER,
            "Deleted Comfy pending prompt for generation job",
            job_id=job.job_id,
            prompt_id=job.prompt_id,
        )

    def _log_unexpected_external_comfy_work(self) -> None:
        """Log Comfy queue prompt ids that are not owned by Substitute queue state."""

        get_queue = getattr(self._dispatcher, "get_comfy_queue_snapshot", None)
        if not callable(get_queue):
            return
        try:
            snapshot = get_queue()
        except Exception as error:
            log_warning(
                _LOGGER,
                "Comfy queue reconciliation failed",
                error=str(error),
            )
            return
        owned_prompt_ids = {
            job.prompt_id for job in self._jobs if job.prompt_id is not None
        }
        external_running = tuple(
            prompt_id
            for prompt_id in snapshot.running_prompt_ids
            if prompt_id not in owned_prompt_ids
        )
        external_pending = tuple(
            prompt_id
            for prompt_id in snapshot.pending_prompt_ids
            if prompt_id not in owned_prompt_ids
        )
        if not external_running and not external_pending:
            return
        log_warning(
            _LOGGER,
            "Comfy queue contains prompts not owned by Substitute",
            external_running_prompt_ids=external_running,
            external_pending_prompt_ids=external_pending,
        )

    def _mark_completed(self, job_id: str) -> None:
        """Mark one active job completed and continue queue dispatch."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        self._replace_job(job_id, status="completed", completed_at=self._clock())
        self._callbacks_by_job_id.pop(job_id, None)
        self._dispatch_tokens_by_job_id.pop(job_id, None)
        if self._active_job_id == job_id:
            self._active_job_id = None
        self._notify_lifecycle(job_id, "completed")
        self._prune_terminal_history()
        self._notify_structural_observers(changed_job_id=job_id)
        self._dispatch_next_if_idle()

    def _mark_failed(
        self,
        job_id: str,
        message: str,
        *,
        detail: str | None = None,
    ) -> None:
        """Mark one active job failed and continue queue dispatch."""

        job = self._job_by_id(job_id)
        if job is None or job.status in TERMINAL_GENERATION_JOB_STATUSES:
            return
        self._replace_job(
            job_id,
            status="failed",
            failure_message=message,
            failure_summary=summarize_generation_failure(message, detail=detail),
            failure_detail=detail,
            completed_at=self._clock(),
        )
        self._callbacks_by_job_id.pop(job_id, None)
        self._dispatch_tokens_by_job_id.pop(job_id, None)
        if self._active_job_id == job_id:
            self._active_job_id = None
        self._notify_lifecycle(job_id, "failed")
        self._prune_terminal_history()
        self._notify_structural_observers(changed_job_id=job_id)
        self._dispatch_next_if_idle()

    def _replace_job(
        self,
        job_id: str,
        *,
        status: GenerationJobStatus | None = None,
        prompt_id: str | None = None,
        generation_run_id: str | None = None,
        client_id: str | None = None,
        failure_message: str | None = None,
        failure_summary: str | None = None,
        failure_detail: str | None = None,
        output_run_number: int | None = None,
        output_bucket_key: str | None = None,
        output_bucket_directory: Path | None = None,
        output_bucket_label: str | None = None,
        progress_percent: float | None = None,
        output_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        last_output_path: Path | None = None,
        last_output_node_id: str | None = None,
        execution_duration_ms: float | None = None,
        cube_execution_durations: (
            tuple[GenerationCubeExecutionDuration, ...] | None
        ) = None,
    ) -> None:
        """Replace one job in-place while preserving immutable DTO semantics."""

        index = self._index_by_id(job_id)
        if index is None:
            return
        current = self._jobs[index]
        self._jobs[index] = replace(
            current,
            status=status if status is not None else current.status,
            prompt_id=prompt_id if prompt_id is not None else current.prompt_id,
            generation_run_id=(
                generation_run_id
                if generation_run_id is not None
                else current.generation_run_id
            ),
            client_id=client_id if client_id is not None else current.client_id,
            failure_message=(
                failure_message
                if failure_message is not None
                else current.failure_message
            ),
            failure_summary=(
                failure_summary
                if failure_summary is not None
                else current.failure_summary
            ),
            failure_detail=(
                failure_detail if failure_detail is not None else current.failure_detail
            ),
            output_run_number=(
                output_run_number
                if output_run_number is not None
                else current.output_run_number
            ),
            output_bucket_key=(
                output_bucket_key
                if output_bucket_key is not None
                else current.output_bucket_key
            ),
            output_bucket_directory=(
                output_bucket_directory
                if output_bucket_directory is not None
                else current.output_bucket_directory
            ),
            output_bucket_label=(
                output_bucket_label
                if output_bucket_label is not None
                else current.output_bucket_label
            ),
            progress_percent=(
                progress_percent
                if progress_percent is not None
                else current.progress_percent
            ),
            output_count=output_count
            if output_count is not None
            else current.output_count,
            started_at=started_at if started_at is not None else current.started_at,
            completed_at=(
                completed_at if completed_at is not None else current.completed_at
            ),
            last_output_path=(
                last_output_path
                if last_output_path is not None
                else current.last_output_path
            ),
            last_output_node_id=(
                last_output_node_id
                if last_output_node_id is not None
                else current.last_output_node_id
            ),
            execution_duration_ms=(
                execution_duration_ms
                if execution_duration_ms is not None
                else current.execution_duration_ms
            ),
            cube_execution_durations=(
                cube_execution_durations
                if cube_execution_durations is not None
                else current.cube_execution_durations
            ),
        )
        self._invalidate_projected_jobs()

    def _replace_job_progress(
        self,
        job_id: str,
        *,
        progress_percent: float,
    ) -> None:
        """Replace one job's progress while preserving projection validity."""

        index = self._index_by_id(job_id)
        if index is None:
            return
        current = self._jobs[index]
        self._jobs[index] = replace(current, progress_percent=progress_percent)
        self._patch_projected_job_progress(
            job_id=job_id,
            progress_percent=progress_percent,
        )

    def _patch_projected_job_progress(
        self,
        *,
        job_id: str,
        progress_percent: float,
    ) -> None:
        """Patch cached projected queue state after a progress-only change."""

        if self._projected_jobs_cache is None:
            return
        self._projected_jobs_cache = tuple(
            replace(job, progress_percent=progress_percent)
            if job.job_id == job_id
            else job
            for job in self._projected_jobs_cache
        )

    def _job_by_id(self, job_id: str) -> GenerationQueueJob | None:
        """Return one job by id when present."""

        index = self._index_by_id(job_id)
        if index is None:
            return None
        return self._jobs[index]

    def _index_by_id(self, job_id: str) -> int | None:
        """Return one job index by id when present."""

        for index, job in enumerate(self._jobs):
            if job.job_id == job_id:
                return index
        return None

    def _notify_structural_observers(
        self,
        *,
        changed_job_id: str | None = None,
    ) -> None:
        """Publish a structural queue change to registered observers."""

        if not self._observers:
            return
        state = self.jobs()
        event = GenerationQueueStateChange(
            jobs=state,
            change_kind="structural",
            changed_job_id=changed_job_id,
        )
        for observer in list(self._observers):
            observer(event)

    def _notify_progress_observers(self, *, changed_job_id: str) -> None:
        """Publish a progress-only queue change to registered observers."""

        if not self._observers:
            return
        state = self.jobs()
        event = GenerationQueueStateChange(
            jobs=state,
            change_kind="progress",
            changed_job_id=changed_job_id,
        )
        for observer in list(self._observers):
            observer(event)

    def _notify_lifecycle(
        self,
        job_id: str,
        action: GenerationJobLifecycleAction,
    ) -> None:
        """Publish one detailed queue lifecycle transition."""

        if not self._lifecycle_observers:
            return
        job = self._job_by_id(job_id)
        if job is None:
            return
        event = GenerationJobLifecycleEvent(action=action, job=job)
        for observer in list(self._lifecycle_observers):
            observer(event)

    def _prune_terminal_history(self) -> None:
        """Drop oldest terminal jobs beyond the configured retention limit."""

        if self._terminal_history_limit < 0:
            return
        terminal_indices = [
            index
            for index, job in enumerate(self._jobs)
            if job.status in TERMINAL_GENERATION_JOB_STATUSES
        ]
        overflow = len(terminal_indices) - self._terminal_history_limit
        if overflow <= 0:
            return
        oldest_terminal_indices = sorted(
            terminal_indices,
            key=lambda index: (
                self._jobs[index].completed_at or self._jobs[index].created_at,
                self._jobs[index].job_id,
            ),
        )
        pruned_indices = set(oldest_terminal_indices[:overflow])
        pruned_job_ids = [self._jobs[index].job_id for index in pruned_indices]
        self._jobs = [
            job for index, job in enumerate(self._jobs) if index not in pruned_indices
        ]
        for job_id in pruned_job_ids:
            self._callbacks_by_job_id.pop(job_id, None)
            self._outputs_by_job_id.pop(job_id, None)
        log_info(
            _LOGGER,
            "Pruned terminal generation queue history",
            pruned_count=len(pruned_job_ids),
            terminal_history_limit=self._terminal_history_limit,
        )
        self._invalidate_projected_jobs()


def _progress_event_matches_job(
    job: GenerationQueueJob,
    event: ProgressUpdate,
) -> bool:
    """Return whether progress identity belongs to one queued job."""

    return (
        event.workflow_id == job.snapshot.workflow_id
        and (
            job.generation_run_id is None
            or event.generation_run_id == job.generation_run_id
        )
        and (job.prompt_id is None or event.prompt_id == job.prompt_id)
        and (job.client_id is None or event.client_id == job.client_id)
    )


__all__ = [
    "ACTIVE_GENERATION_JOB_STATUSES",
    "CANCELLABLE_GENERATION_JOB_STATUSES",
    "GenerationQueueChangeKind",
    "GenerationJobLifecycleAction",
    "GenerationJobLifecycleEvent",
    "GenerationJobLifecycleObserver",
    "GenerationJobQueueService",
    "GenerationQueueBatchEntry",
    "GenerationQueueStateChange",
    "OutputRunProjectionCacheKeyProvider",
    "PreparedGenerationDispatcher",
    "QueueProjectionCacheKey",
    "QueueBatchContext",
    "QueueObserver",
]
