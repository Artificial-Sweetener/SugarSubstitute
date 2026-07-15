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

"""Contract tests for workspace generation presentation controller behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationPreparationResult,
    GenerationRequest,
    GenerationService,
)
from tests.execution_testing import QueuedTaskSubmitter
from substitute.application.generation.job_queue_service import (
    GenerationQueueBatchEntry,
)
from substitute.application.errors import ErrorReportKind
from substitute.application.ports import (
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.generation_action_projection import (
    project_generation_actions,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationActionState,
)
from substitute.presentation.shell.workspace_controller import (
    GenerationPreflightError,
    GenerationUiBindings,
    QueuedGenerationPreparationJob,
    WorkspaceGenerationController,
)
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationPreparationExecutor,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    WorkspaceGenerationActions,
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


def test_generation_preparation_executor_close_cancels_and_suppresses_callbacks() -> (
    None
):
    """Closing generation preparation should cancel scoped work and drop callbacks."""

    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    completed: list[GenerationPreparationResult] = []
    failed: list[BaseException] = []
    executor = GenerationPreparationExecutor(
        submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )

    executor.submit(
        prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
        on_completed=completed.append,
        on_failed=failed.append,
    )

    assert len(submitter.handles) == 1
    assert submitter.handles[0].state == "pending"

    executor.close()

    assert close_calls == ["closed"]
    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "generation_preparation_executor_closed"
    assert submitter.handles[0].state == "cancelled"
    assert completed == []
    assert failed == []

    try:
        executor.submit(
            prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
            on_completed=completed.append,
            on_failed=failed.append,
        )
    except RuntimeError as error:
        assert "closed" in str(error)
    else:
        raise AssertionError("closed generation preparation accepted new work")


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
        clear_output_for_workflow=lambda workflow_id: (
            recorder.clear_output_calls.append(workflow_id)
        ),
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


def _bindings_with_snapshots(
    recorder: _BindingRecorder,
    snapshots: tuple[GenerationJobSnapshot, ...],
) -> GenerationUiBindings:
    """Return bindings that expose queued snapshots for controller tests."""

    bindings = _build_bindings(recorder)
    return GenerationUiBindings(
        build_generation_request=bindings.build_generation_request,
        randomize_seeds=bindings.randomize_seeds,
        clear_output_for_workflow=bindings.clear_output_for_workflow,
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


def test_handle_generate_clicked_starts_continuous_mode_when_inactive() -> None:
    """Continuous mode should enter stop mode and enqueue one queued snapshot."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    snapshot = _snapshot()
    bindings = _bindings_with_snapshots(recorder, (snapshot,))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    assert controller.is_continuous_active is True
    assert recorder.refresh_requests == ["refresh"]
    assert fake_service.single_call_args == []
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [snapshot]
    assert isinstance(fake_queue.enqueue_calls[0]["callbacks"], GenerationCallbacks)


def test_handle_generate_clicked_ignores_batch_count_in_continuous_mode() -> None:
    """Continuous start should enqueue one cycle rather than batch-multiplying it."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    build_calls = 0

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        nonlocal build_calls
        build_calls += 1
        return (_snapshot("Continuous"),)

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        effective_batch_count=lambda: 5,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    assert build_calls == 1
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("Continuous")
    ]


def test_handle_generate_clicked_stops_continuous_mode_when_active() -> None:
    """Continuous mode click should stop the loop and restore continuous mode."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    assert controller.is_continuous_active is False
    assert fake_service.interrupt_calls == 0
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_handle_generate_clicked_runs_single_generation_in_generate_mode() -> None:
    """Generate mode click should dispatch one request through generation service."""
    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert len(fake_service.single_call_args) == 1
    call = fake_service.single_call_args[0]
    assert isinstance(call["request"], GenerationRequest)
    assert isinstance(call["callbacks"], GenerationCallbacks)
    assert recorder.refresh_requests == []


def test_handle_generate_clicked_ignores_batch_without_queue_service() -> None:
    """Direct generation should remain a single dispatch even with batch count."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        effective_batch_count=lambda: 4,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert len(fake_service.single_call_args) == 1
    assert recorder.build_request_calls == 1


def test_handle_generate_clicked_enqueues_snapshot_when_queue_is_available() -> None:
    """Generate mode should enqueue a snapshot instead of dispatching immediately."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    snapshot = GenerationJobSnapshot(
        workflow_id="wf-1",
        workflow_name="Workflow 1",
        sugar_script_text="# queued script",
    )
    bindings = _build_bindings(recorder)
    bindings = GenerationUiBindings(
        build_generation_request=bindings.build_generation_request,
        randomize_seeds=bindings.randomize_seeds,
        clear_output_for_workflow=bindings.clear_output_for_workflow,
        on_progress=bindings.on_progress,
        on_model_load_progress=bindings.on_model_load_progress,
        on_preview=bindings.on_preview,
        on_output_image=bindings.on_output_image,
        on_failure=bindings.on_failure,
        on_timing=bindings.on_timing,
        on_completed=bindings.on_completed,
        refresh_generation_actions=bindings.refresh_generation_actions,
        build_queued_generation_snapshots=lambda: (snapshot,),
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert len(fake_queue.enqueue_calls) == 1
    assert fake_queue.enqueue_calls[0]["snapshot"] == snapshot
    assert isinstance(fake_queue.enqueue_calls[0]["callbacks"], GenerationCallbacks)


def test_handle_generate_clicked_submits_captured_preparation_without_blocking() -> (
    None
):
    """Queued Generate should return before preparation tasks run."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    fake_executor = _FakePreparationExecutor()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
        preparation_executor=cast(Any, fake_executor),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    prepare_runs = 0
    prepared_hooks = 0
    snapshot = _snapshot("Async")

    def _capture_preparation() -> QueuedGenerationPreparationJob:
        def _prepare() -> GenerationPreparationResult:
            nonlocal prepare_runs
            prepare_runs += 1
            return GenerationPreparationResult(snapshots=(snapshot,))

        def _on_prepared(
            result: GenerationPreparationResult,
        ) -> tuple[GenerationJobSnapshot, ...]:
            nonlocal prepared_hooks
            prepared_hooks += 1
            return result.snapshots

        return QueuedGenerationPreparationJob(
            prepare_snapshots=_prepare,
            on_prepared=_on_prepared,
        )

    def _unexpected_sync_build() -> tuple[GenerationJobSnapshot, ...]:
        """Fail if the async preparation path falls back to sync building."""

        raise AssertionError("sync build should not run")

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        build_queued_generation_snapshots=_unexpected_sync_build,
        capture_queued_generation_preparation=_capture_preparation,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert prepare_runs == 0
    assert prepared_hooks == 0
    assert fake_queue.enqueue_calls == []
    assert len(fake_executor.submissions) == 1

    fake_executor.complete(0)

    assert prepare_runs == 1
    assert prepared_hooks == 1
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [snapshot]


def test_captured_preparation_enqueues_multi_scene_result_as_one_batch() -> None:
    """Task-prepared scene snapshots should enter the queue in one transaction."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    fake_executor = _FakePreparationExecutor()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
        preparation_executor=cast(Any, fake_executor),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    scene_snapshots = (
        _snapshot("Scene A"),
        _snapshot("Scene B"),
        _snapshot("Scene C"),
    )

    def _capture_preparation() -> QueuedGenerationPreparationJob:
        def _prepare() -> GenerationPreparationResult:
            return GenerationPreparationResult(
                snapshots=scene_snapshots,
                scene_run_id="scene-run",
                scene_count=len(scene_snapshots),
            )

        def _on_prepared(
            result: GenerationPreparationResult,
        ) -> tuple[GenerationJobSnapshot, ...]:
            return result.snapshots

        return QueuedGenerationPreparationJob(
            prepare_snapshots=_prepare,
            on_prepared=_on_prepared,
        )

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        capture_queued_generation_preparation=_capture_preparation,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)
    fake_executor.complete(0)

    assert len(fake_queue.batch_entry_calls) == 1
    assert [entry.snapshot for entry in fake_queue.batch_entry_calls[0]] == list(
        scene_snapshots
    )
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == list(
        scene_snapshots
    )


def test_handle_generate_clicked_enqueues_independent_batch_snapshots() -> None:
    """Batch generation should rebuild queued snapshots for each batch member."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    build_calls = 0

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        nonlocal build_calls
        build_calls += 1
        return (_snapshot(f"Batch {build_calls}"),)

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        effective_batch_count=lambda: 3,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert build_calls == 3
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("Batch 1"),
        _snapshot("Batch 2"),
        _snapshot("Batch 3"),
    ]


def test_handle_generate_clicked_multiplies_scene_snapshots_by_batch_count() -> None:
    """Batch count should multiply workflows that materialize multiple scenes."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    build_calls = 0

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        nonlocal build_calls
        build_calls += 1
        return (
            _snapshot(f"Batch {build_calls} scene A"),
            _snapshot(f"Batch {build_calls} scene B"),
        )

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        effective_batch_count=lambda: 3,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert build_calls == 3
    assert len(fake_queue.batch_entry_calls) == 3
    assert [
        [entry.snapshot for entry in entries]
        for entries in fake_queue.batch_entry_calls
    ] == [
        [_snapshot("Batch 1 scene A"), _snapshot("Batch 1 scene B")],
        [_snapshot("Batch 2 scene A"), _snapshot("Batch 2 scene B")],
        [_snapshot("Batch 3 scene A"), _snapshot("Batch 3 scene B")],
    ]
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("Batch 1 scene A"),
        _snapshot("Batch 1 scene B"),
        _snapshot("Batch 2 scene A"),
        _snapshot("Batch 2 scene B"),
        _snapshot("Batch 3 scene A"),
        _snapshot("Batch 3 scene B"),
    ]


def test_handle_generate_clicked_enqueues_queued_snapshots_in_order() -> None:
    """Generate mode should enqueue each prepared snapshot through the normal queue."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    snapshots = (
        GenerationJobSnapshot(
            workflow_id="wf-1",
            workflow_name="Workflow 1 - portrait",
            sugar_script_text="# portrait",
        ),
        GenerationJobSnapshot(
            workflow_id="wf-1",
            workflow_name="Workflow 1 - cafe",
            sugar_script_text="# cafe",
        ),
    )
    bindings = _build_bindings(recorder)
    bindings = GenerationUiBindings(
        build_generation_request=bindings.build_generation_request,
        randomize_seeds=bindings.randomize_seeds,
        clear_output_for_workflow=bindings.clear_output_for_workflow,
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

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert len(fake_queue.batch_entry_calls) == 1
    assert [entry.snapshot for entry in fake_queue.batch_entry_calls[0]] == list(
        snapshots
    )
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == list(snapshots)
    assert all(
        isinstance(call["callbacks"], GenerationCallbacks)
        for call in fake_queue.enqueue_calls
    )


def test_handle_generate_clicked_blocks_queued_generation_when_backend_is_starting() -> (
    None
):
    """Queued generation should block before snapshot building while backend starts."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    controller.set_backend_available(False, message="ComfyUI is still starting.")
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_queue.enqueue_calls == []
    assert recorder.build_request_calls == 0
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].message == "ComfyUI is still starting."
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.kind is ErrorReportKind.COMFY_CONNECTION


def test_handle_generate_clicked_reports_queued_snapshot_preflight_failure() -> None:
    """Queued Generate should route snapshot preflight failures without enqueueing."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)
    bindings = GenerationUiBindings(
        build_generation_request=bindings.build_generation_request,
        randomize_seeds=bindings.randomize_seeds,
        clear_output_for_workflow=bindings.clear_output_for_workflow,
        on_progress=bindings.on_progress,
        on_model_load_progress=bindings.on_model_load_progress,
        on_preview=bindings.on_preview,
        on_output_image=bindings.on_output_image,
        on_failure=bindings.on_failure,
        on_timing=bindings.on_timing,
        on_completed=bindings.on_completed,
        refresh_generation_actions=bindings.refresh_generation_actions,
        build_queued_generation_snapshots=lambda: (_ for _ in ()).throw(
            GenerationPreflightError(
                workflow_id="wf-a",
                message="missing snapshots",
            )
        ),
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_queue.enqueue_calls == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].workflow_id == "wf-a"
    assert recorder.failures[0].message == "missing snapshots"
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.kind is ErrorReportKind.SUBSTITUTE_INTERNAL
    assert recorder.failures[0].error_report.operation_context is not None
    assert recorder.failures[0].error_report.operation_context.operation == (
        "queue_generation"
    )


def test_handle_generate_clicked_stops_batch_after_snapshot_preflight_failure() -> None:
    """Batch enqueue should stop after the first snapshot preflight failure."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    build_calls = 0

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        nonlocal build_calls
        build_calls += 1
        if build_calls == 1:
            return (_snapshot("Before failure"),)
        raise GenerationPreflightError(
            workflow_id="wf-a",
            message="batch preflight failed",
        )

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        effective_batch_count=lambda: 3,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert build_calls == 2
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("Before failure")
    ]
    assert len(recorder.failures) == 1
    assert recorder.failures[0].message == "batch preflight failed"


def test_handle_generate_clicked_reports_missing_queue_snapshot_binding() -> None:
    """Queued Generate should fail clearly when snapshot binding is unavailable."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert fake_queue.enqueue_calls == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].workflow_id == "queue"
    assert recorder.failures[0].error_report is not None


def test_handle_generate_clicked_blocks_when_backend_is_starting() -> None:
    """Generate clicks should fail preflight while Comfy backend is unavailable."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))
    controller.set_backend_available(False, message="ComfyUI is still starting.")
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert recorder.build_request_calls == 0
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].message == "ComfyUI is still starting."
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.kind is ErrorReportKind.COMFY_CONNECTION


def test_handle_generate_clicked_blocks_continuous_start_when_backend_is_starting() -> (
    None
):
    """Continuous generation should not start until backend readiness is available."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))
    controller.set_backend_available(False, message="ComfyUI is still starting.")
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _build_bindings(recorder)

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    assert fake_service.single_call_args == []
    assert controller.is_continuous_active is False
    assert recorder.refresh_requests == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.kind is ErrorReportKind.COMFY_CONNECTION


def test_handle_generate_clicked_reports_preflight_failure_without_dispatch() -> None:
    """Generate mode should route preflight failures without calling generation service."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))
    recorder = _BindingRecorder([], [], [], [], [], [])

    def _raise_preflight() -> GenerationRequest:
        raise GenerationPreflightError(
            workflow_id="wf-a",
            message="dirty mask save failed",
        )

    bindings = GenerationUiBindings(
        build_generation_request=_raise_preflight,
        randomize_seeds=lambda: None,
        clear_output_for_workflow=lambda _workflow_id: None,
        on_progress=lambda event: recorder.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: recorder.previews.append(event),
        on_output_image=lambda event: recorder.outputs.append(event),
        on_failure=lambda failure: recorder.failures.append(failure),
        on_timing=lambda event: recorder.timing.append(event),
        on_completed=lambda _event: None,
        refresh_generation_actions=lambda: recorder.refresh_requests.append("refresh"),
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].workflow_id == "wf-a"
    assert recorder.failures[0].message == "dirty mask save failed"
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.kind is ErrorReportKind.SUBSTITUTE_INTERNAL
    assert recorder.failures[0].error_report.operation_context is not None
    assert recorder.failures[0].error_report.operation_context.operation == "generate"


def test_handle_generate_clicked_reports_snapshot_preflight_failure_without_enqueue() -> (
    None
):
    """Queued Generate should route snapshot preflight failures without enqueueing."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])

    def _raise_preflight() -> GenerationJobSnapshot:
        raise GenerationPreflightError(
            workflow_id="wf-a",
            message="dirty mask save failed",
        )

    bindings = GenerationUiBindings(
        build_generation_request=lambda: GenerationRequest(
            workflow_id="wf-a",
            workflow_name="Workflow A",
            workflow=cast(Any, object()),
        ),
        randomize_seeds=lambda: None,
        clear_output_for_workflow=lambda _workflow_id: None,
        on_progress=lambda event: recorder.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: recorder.previews.append(event),
        on_output_image=lambda event: recorder.outputs.append(event),
        on_failure=lambda failure: recorder.failures.append(failure),
        on_timing=lambda event: recorder.timing.append(event),
        on_completed=lambda _event: None,
        refresh_generation_actions=lambda: recorder.refresh_requests.append("refresh"),
        build_queued_generation_snapshots=lambda: (_raise_preflight(),),
    )

    controller.handle_generate_clicked(current_mode="generate", bindings=bindings)

    assert fake_service.single_call_args == []
    assert fake_queue.enqueue_calls == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "preflight"
    assert recorder.failures[0].workflow_id == "wf-a"
    assert recorder.failures[0].message == "dirty mask save failed"
    assert recorder.failures[0].error_report is not None
    assert recorder.failures[0].error_report.operation_context is not None
    assert recorder.failures[0].error_report.operation_context.operation == (
        "queue_generation"
    )


def test_continuous_completion_enqueues_next_snapshot_after_ui_completion() -> None:
    """Continuous completion should run UI cleanup before enqueueing the next cycle."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    snapshots = [_snapshot("First"), _snapshot("Second")]
    base_bindings = _build_bindings(recorder)

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        return (snapshots.pop(0),)

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    first_callbacks = cast(
        GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"]
    )

    first_callbacks.on_completed(_completed("wf-1"))

    assert controller.is_continuous_active is True
    assert recorder.completed == [_completed("wf-1")]
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("First"),
        _snapshot("Second"),
    ]


def test_continuous_scene_cycle_requeues_only_after_last_scene_snapshot() -> None:
    """Continuous scene cycles should requeue after the final scene completes."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    first_scene = _snapshot("First scene")
    second_scene = _snapshot("Second scene")
    next_cycle = _snapshot("Next cycle")
    cycles = [(first_scene, second_scene), (next_cycle,)]
    base_bindings = _build_bindings(recorder)

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        return cycles.pop(0)

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    assert len(fake_queue.batch_entry_calls) == 1
    first_callbacks = cast(
        GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"]
    )
    second_callbacks = cast(
        GenerationCallbacks, fake_queue.enqueue_calls[1]["callbacks"]
    )

    first_callbacks.on_completed(_completed("wf-1"))
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        first_scene,
        second_scene,
    ]

    second_callbacks.on_completed(_completed("wf-1"))

    assert len(fake_queue.batch_entry_calls) == 2
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        first_scene,
        second_scene,
        next_cycle,
    ]
    assert recorder.completed == [_completed("wf-1"), _completed("wf-1")]


def test_continuous_stop_before_completion_prevents_requeue() -> None:
    """Stopping continuous mode should make later completion callbacks inert."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    callbacks = cast(GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"])
    controller.stop_continuous_generation(bindings=bindings)

    callbacks.on_completed(_completed("wf-1"))

    assert controller.is_continuous_active is False
    assert len(fake_queue.enqueue_calls) == 1
    assert recorder.completed == [_completed("wf-1")]
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_continuous_cancel_before_completion_prevents_requeue() -> None:
    """Queue cancellation should prevent stale terminal callbacks from requeueing."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    callbacks = cast(GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"])
    controller.cancel_generation_queue()

    callbacks.on_completed(_completed("wf-1"))

    assert controller.is_continuous_active is False
    assert fake_queue.cancel_all_calls == 1
    assert len(fake_queue.enqueue_calls) == 1
    assert recorder.completed == [_completed("wf-1")]


def test_continuous_failure_stops_loop_and_reports_failure() -> None:
    """Continuous job failure should restore continuous mode and avoid requeue."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    callbacks = cast(GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"])
    callbacks.on_failure(
        GenerationFailure(stage="listen", workflow_id="wf-1", message="failed")
    )

    assert controller.is_continuous_active is False
    assert len(fake_queue.enqueue_calls) == 1
    assert len(recorder.failures) == 1
    assert recorder.failures[0].message == "failed"
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_continuous_next_snapshot_preflight_failure_stops_loop() -> None:
    """Next-cycle snapshot preflight failure should stop and report the failure."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _build_bindings(recorder)
    calls = 0

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return (_snapshot(),)
        raise GenerationPreflightError(
            workflow_id="wf-1",
            message="next snapshot failed",
        )

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    callbacks = cast(GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"])
    callbacks.on_completed(_completed("wf-1"))

    assert controller.is_continuous_active is False
    assert len(fake_queue.enqueue_calls) == 1
    assert recorder.completed == [_completed("wf-1")]
    assert len(recorder.failures) == 1
    assert recorder.failures[0].message == "next snapshot failed"
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_continuous_start_reports_empty_snapshot_cycle() -> None:
    """Continuous start should fail closed when no snapshots are prepared."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, ())

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    assert controller.is_continuous_active is False
    assert fake_queue.enqueue_calls == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].workflow_id == "queue"
    assert "prepared no jobs" in recorder.failures[0].message
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_continuous_callbacks_route_generation_events() -> None:
    """Continuous queue callbacks should bridge progress, preview, output, and failure."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    callbacks = cast(GenerationCallbacks, fake_queue.enqueue_calls[0]["callbacks"])
    assert callbacks.randomize_seeds is None
    callbacks.clear_output("wf-1")
    callbacks.on_progress(_progress_update(workflow_percent=50.0, sampler_percent=25.0))
    callbacks.on_preview(PreviewImageUpdate(workflow_id="wf-1", image=object()))
    callbacks.on_output_image(
        OutputImageUpdate(
            workflow_id="wf-1",
            workflow_payload={"N1": {"class_type": "KSampler"}},
            file_path=Path("out.png"),
            node_id="N1",
        )
    )
    callbacks.on_failure(
        GenerationFailure(stage="queue", workflow_id="wf-1", message="failed")
    )

    assert recorder.clear_output_calls == ["wf-1"]
    assert recorder.progress == [
        _progress_update(workflow_percent=50.0, sampler_percent=25.0)
    ]
    assert len(recorder.previews) == 1
    assert len(recorder.outputs) == 1
    assert len(recorder.failures) == 1


def test_interrupt_generation_delegates_to_generation_service() -> None:
    """Interrupt flow should delegate directly to generation service."""
    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))

    result = controller.interrupt_generation()

    assert result == InterruptResult(status="sent", status_code=200, error=None)
    assert fake_service.interrupt_calls == 1


def test_skip_active_queue_job_delegates_to_queue_service() -> None:
    """Skip should delegate to the generation queue when queueing is enabled."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )

    controller.skip_active_queue_job()

    assert fake_queue.skip_calls == 1
    assert fake_service.interrupt_calls == 0


def test_continuous_skip_requeues_when_cycle_is_empty() -> None:
    """Skipping the final continuous job should schedule the next cycle."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService(cancellable_jobs_available=False)
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    snapshots = [_snapshot("First"), _snapshot("Second")]
    base_bindings = _build_bindings(recorder)

    def _build_snapshots() -> tuple[GenerationJobSnapshot, ...]:
        return (snapshots.pop(0),)

    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=base_bindings.refresh_generation_actions,
        build_queued_generation_snapshots=_build_snapshots,
    )

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    controller.skip_active_queue_job(bindings=bindings)

    assert controller.is_continuous_active is True
    assert fake_queue.skip_calls == 1
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        _snapshot("First"),
        _snapshot("Second"),
    ]
    assert recorder.failures == []
    assert recorder.refresh_requests == ["refresh", "refresh"]


def test_continuous_skip_does_not_requeue_when_cycle_work_remains() -> None:
    """Skipping one scene should let remaining queued scene work continue."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService(cancellable_jobs_available=True)
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    first_scene = _snapshot("First scene")
    second_scene = _snapshot("Second scene")
    bindings = _bindings_with_snapshots(recorder, (first_scene, second_scene))

    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    controller.skip_active_queue_job(bindings=bindings)

    assert controller.is_continuous_active is True
    assert fake_queue.skip_calls == 1
    assert [call["snapshot"] for call in fake_queue.enqueue_calls] == [
        first_scene,
        second_scene,
    ]
    assert recorder.failures == []


def test_skip_active_queue_job_noops_without_queue_service() -> None:
    """Skip should stay scoped to queued generation work."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))

    controller.skip_active_queue_job()

    assert fake_service.interrupt_calls == 0


def test_cancel_generation_queue_delegates_to_queue_service() -> None:
    """Stop-all should cancel queued jobs when queueing is enabled."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )

    result = controller.cancel_generation_queue()

    assert result is None
    assert fake_queue.cancel_all_calls == 1
    assert fake_service.interrupt_calls == 0


def test_cancel_generation_queue_stops_continuous_generation_before_queue_cancel() -> (
    None
):
    """Stop-all should stop continuous mode before cancelling queued jobs."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    recorder = _BindingRecorder([], [], [], [], [], [])
    bindings = _bindings_with_snapshots(recorder, (_snapshot(),))
    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)

    result = controller.cancel_generation_queue()

    assert result is None
    assert controller.is_continuous_active is False
    assert fake_service.interrupt_calls == 0
    assert fake_queue.cancel_all_calls == 1


def test_cancel_generation_queue_interrupts_without_queue_service() -> None:
    """Stop-all should preserve interrupt fallback when queueing is unavailable."""

    fake_service = _FakeGenerationService()
    controller = WorkspaceGenerationController(cast(GenerationService, fake_service))

    result = controller.cancel_generation_queue()

    assert result == InterruptResult(status="sent", status_code=200, error=None)
    assert fake_service.interrupt_calls == 1


def test_workspace_skip_click_skips_active_queue_job() -> None:
    """Workspace skip intent should route to the generation controller."""

    bindings = object()
    skip_calls: list[object | None] = []
    progress_clear_calls: list[bool] = []
    retire_calls: list[str] = []
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "skip_active_queue_job": lambda self, *, bindings: (
                        skip_calls.append(bindings)
                    )
                },
            )(),
            "generation_job_queue_service": type(
                "Queue",
                (),
                {"has_active_job": lambda self: False},
            )(),
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_skip_generation_clicked()

    assert skip_calls == [bindings]
    assert retire_calls == ["skipped"]
    assert progress_clear_calls == [True]


def test_workspace_skip_click_keeps_generation_progress_when_queue_has_active_job() -> (
    None
):
    """Workspace skip should keep progress while replacement queue work is active."""

    bindings = object()
    skip_calls: list[object | None] = []
    progress_clear_calls: list[bool] = []
    retire_calls: list[str] = []
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "skip_active_queue_job": lambda self, *, bindings: (
                        skip_calls.append(bindings)
                    )
                },
            )(),
            "generation_job_queue_service": type(
                "Queue",
                (),
                {"has_active_job": lambda self: True},
            )(),
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_skip_generation_clicked()

    assert skip_calls == [bindings]
    assert retire_calls == ["skipped"]
    assert progress_clear_calls == []


def test_workspace_interrupt_click_clears_generation_progress_after_success() -> None:
    """Workspace interrupt should clear progress after a successful interrupt."""

    clear_calls: list[str] = []
    interrupt_calls: list[bool] = []
    retire_calls: list[str] = []
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "interrupt_generation": lambda self: (
                        interrupt_calls.append(True),
                        InterruptResult(status="sent", status_code=200, error=None),
                    )[1],
                },
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append("model_fields")
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: clear_calls.append(
                        "generation_progress"
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, None),
    ).on_interrupt_clicked()

    assert interrupt_calls == [True]
    assert retire_calls == ["interrupted"]
    assert clear_calls == ["model_fields", "generation_progress"]


def test_workspace_stop_click_cancels_generation_queue() -> None:
    """Workspace stop intent should request queue-wide cancellation and clear progress."""

    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    cancel_calls: list[object | None] = []
    retire_calls: list[str] = []
    bindings = object()
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "cancel_generation_queue": lambda self, *, bindings: (
                        cancel_calls.append(bindings),
                        None,
                    )[1],
                },
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_stop_generation_clicked()

    assert cancel_calls == [bindings]
    assert retire_calls == ["stopped"]
    assert clear_calls == [True]
    assert progress_clear_calls == [True]


def test_workspace_stop_click_reprojects_active_continuous_as_inactive() -> None:
    """Stop-all should restore continuous visuals through state projection."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    presentations: list[GenerationActionPresentation] = []

    def _record_projection() -> None:
        presentations.append(
            project_generation_actions(
                GenerationActionState(
                    selected_mode="continuous",
                    continuous_active=controller.is_continuous_active,
                    backend_ready=True,
                    workflow_runnable=True,
                    settings_route_active=False,
                    queue_has_active=fake_queue.has_active_job(),
                    queue_has_cancellable=fake_queue.has_cancellable_jobs(),
                    pending_queue_count=0,
                    queue_has_visible_jobs=False,
                    queue_panel_visible=False,
                )
            )
        )

    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _bindings_with_snapshots(recorder, (_snapshot(),))
    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        clear_output_for_workflow=base_bindings.clear_output_for_workflow,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=_record_projection,
        build_queued_generation_snapshots=base_bindings.build_queued_generation_snapshots,
    )
    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    retire_calls: list[str] = []
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": controller,
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    assert presentations[-1].play_mode == "end_continuous"

    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: bindings,
    ).on_stop_generation_clicked()

    assert controller.is_continuous_active is False
    assert fake_queue.cancel_all_calls == 1
    assert presentations[-1].play_mode == "continuous"
    assert retire_calls == ["stopped"]
    assert clear_calls == [True]
    assert progress_clear_calls == [True]


def test_workspace_stop_click_does_not_clear_generation_progress_after_failed_interrupt() -> (
    None
):
    """Workspace stop should leave progress alone when fallback interrupt fails."""

    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    failure_calls: list[InterruptResult] = []
    retire_calls: list[str] = []
    failed_result = InterruptResult(
        status="failed",
        status_code=500,
        error="boom",
    )
    bindings = object()
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {"cancel_generation_queue": lambda self, *, bindings: failed_result},
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
            "generation_interrupt_failure_presenter": type(
                "FailurePresenter",
                (),
                {
                    "log_interrupt_failure": lambda self, result: failure_calls.append(
                        result
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_stop_generation_clicked()

    assert failure_calls == [failed_result]
    assert retire_calls == []
    assert clear_calls == []
    assert progress_clear_calls == []
