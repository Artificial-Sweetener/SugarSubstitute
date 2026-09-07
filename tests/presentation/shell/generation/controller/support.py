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

"""Provide generation controller test support."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, cast

from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRequest,
)
from substitute.application.generation.job_queue_service import (
    GenerationQueueBatchEntry,
)
from substitute.application.ports import (
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)


@dataclass
class _FakeGenerationService:
    """Capture generation service calls for deterministic controller assertions."""

    def __post_init__(self) -> None:
        """Initialize mutable call-recording collections."""
        self.single_call_args: list[dict[str, object]] = []
        self.interrupt_calls = 0

    def run_single_generation(
        self, *, request: GenerationRequest, callbacks: GenerationCallbacks
    ) -> object:
        """Record single-generation invocations from controller."""
        self.single_call_args.append({"request": request, "callbacks": callbacks})
        return object()

    def interrupt_generation(self) -> InterruptResult:
        """Return deterministic interrupt result while recording invocation count."""
        self.interrupt_calls += 1
        return InterruptResult(status="sent", status_code=200, error=None)


@dataclass
class _FakeGenerationQueueService:
    """Capture queue enqueue calls made by the workspace generation controller."""

    cancellable_jobs_available: bool = False
    active_job_available: bool = False

    def __post_init__(self) -> None:
        """Initialize call recording."""

        self.enqueue_calls: list[dict[str, object]] = []
        self.batch_entry_calls: list[tuple[GenerationQueueBatchEntry, ...]] = []
        self.snapshot_batch_calls: list[dict[str, object]] = []
        self.skip_calls = 0
        self.cancel_all_calls = 0

    def enqueue_snapshot(
        self,
        snapshot: GenerationJobSnapshot,
        callbacks: GenerationCallbacks,
    ) -> object:
        """Record one queue enqueue request."""

        self.enqueue_calls.append({"snapshot": snapshot, "callbacks": callbacks})
        return object()

    def enqueue_snapshot_entries(
        self,
        entries: tuple[GenerationQueueBatchEntry, ...],
    ) -> tuple[object, ...]:
        """Record one batched queue insertion while preserving per-entry callbacks."""

        self.batch_entry_calls.append(entries)
        for entry in entries:
            self.enqueue_snapshot(entry.snapshot, entry.callbacks)
        return tuple(object() for _entry in entries)

    def enqueue_snapshots(
        self,
        snapshots: tuple[GenerationJobSnapshot, ...],
        callbacks: GenerationCallbacks,
    ) -> tuple[object, ...]:
        """Record one same-callback batch insertion."""

        self.snapshot_batch_calls.append(
            {"snapshots": snapshots, "callbacks": callbacks}
        )
        return self.enqueue_snapshot_entries(
            tuple(
                GenerationQueueBatchEntry(snapshot=snapshot, callbacks=callbacks)
                for snapshot in snapshots
            )
        )

    def skip_active_job(self) -> None:
        """Record active queue skip requests."""

        self.skip_calls += 1

    def cancel_all_jobs(self) -> None:
        """Record queue-wide cancellation requests."""

        self.cancel_all_calls += 1

    def has_cancellable_jobs(self) -> bool:
        """Return whether fake queued work remains cancellable."""

        return self.cancellable_jobs_available

    def has_active_job(self) -> bool:
        """Return whether fake queued work remains active."""

        return self.active_job_available


class _FakePreparationExecutor:
    """Capture async preparation submissions for deterministic tests."""

    def __init__(self) -> None:
        """Initialize submitted job storage."""

        self.submissions: list[dict[str, object]] = []

    def submit(
        self,
        *,
        prepare_snapshots: object,
        on_completed: object,
        on_failed: object,
    ) -> None:
        """Record one submitted preparation job without running it."""

        self.submissions.append(
            {
                "prepare_snapshots": prepare_snapshots,
                "on_completed": on_completed,
                "on_failed": on_failed,
            }
        )

    def complete(self, index: int) -> None:
        """Run one submitted job and invoke its success callback."""

        submission = self.submissions[index]
        prepare_snapshots = cast(Any, submission["prepare_snapshots"])
        on_completed = cast(Any, submission["on_completed"])
        on_completed(prepare_snapshots())


@dataclass
class _BindingRecorder:
    """Collect callback invocations emitted from GenerationUiBindings."""

    refresh_requests: list[str]
    progress: list[ProgressUpdate]
    previews: list[PreviewImageUpdate]
    outputs: list[OutputImageUpdate]
    failures: list[GenerationFailure]
    clear_output_calls: list[str]
    randomize_calls: int = 0
    build_request_calls: int = 0
    completed: list[ListenerCompleted] = field(default_factory=list)
    timing: list[GenerationExecutionTiming] = field(default_factory=list)


def _build_bindings(recorder: _BindingRecorder) -> GenerationUiBindings:
    """Construct generation UI bindings with deterministic request payload and capture."""

    def _build_request() -> GenerationRequest:
        recorder.build_request_calls += 1
        return GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=cast(Any, object()),
        )

    def _randomize() -> None:
        recorder.randomize_calls += 1

    return GenerationUiBindings(
        build_generation_request=_build_request,
        randomize_seeds=_randomize,
        on_progress=lambda event: recorder.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: recorder.previews.append(event),
        on_output_image=lambda event: recorder.outputs.append(event),
        on_failure=lambda failure: recorder.failures.append(failure),
        on_timing=lambda event: recorder.timing.append(event),
        on_completed=lambda event: recorder.completed.append(event),
        refresh_generation_actions=lambda: recorder.refresh_requests.append("refresh"),
    )


def _snapshot(name: str = "Workflow 1") -> GenerationJobSnapshot:
    """Return one deterministic queued generation snapshot."""

    return GenerationJobSnapshot(
        workflow_id="wf-1",
        workflow_name=name,
        sugar_script_text=f"# queued {name}",
    )


def _without_output_sessions(
    snapshots: list[GenerationJobSnapshot],
) -> list[GenerationJobSnapshot]:
    """Remove generated session identities for legacy payload comparisons."""

    return [replace(snapshot, output_session_id=None) for snapshot in snapshots]


def _progress_update(
    *,
    workflow_percent: float | None,
    sampler_percent: float | None,
) -> ProgressUpdate:
    """Return one identity-bearing progress update for controller tests."""

    return ProgressUpdate(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
    )


def _completed(workflow_id: str) -> ListenerCompleted:
    """Return one listener completion event for callback tests."""

    return ListenerCompleted(
        workflow_id=workflow_id,
        generation_run_id=f"run-{workflow_id}",
        prompt_id=f"pid-{workflow_id}",
    )


def _emit_completed(
    callbacks: GenerationCallbacks,
    completed: ListenerCompleted,
) -> None:
    """Emit a required completion callback with explicit type narrowing."""

    assert callbacks.on_completed is not None
    callbacks.on_completed(completed)


def _bindings_with_snapshots(
    recorder: _BindingRecorder,
    snapshots: tuple[GenerationJobSnapshot, ...],
) -> GenerationUiBindings:
    """Return bindings that expose queued snapshots for controller tests."""

    bindings = _build_bindings(recorder)
    return GenerationUiBindings(
        build_generation_request=bindings.build_generation_request,
        randomize_seeds=bindings.randomize_seeds,
        on_progress=bindings.on_progress,
        on_model_load_progress=bindings.on_model_load_progress,
        on_preview=bindings.on_preview,
        on_output_image=bindings.on_output_image,
        on_failure=bindings.on_failure,
        on_timing=bindings.on_timing,
        on_completed=bindings.on_completed,
        refresh_generation_actions=bindings.refresh_generation_actions,
        build_queued_generation_snapshots=lambda: snapshots,
    )
