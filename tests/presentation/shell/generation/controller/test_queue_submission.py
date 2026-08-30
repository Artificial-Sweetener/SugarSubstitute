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

from typing import Any, cast

from substitute.application.generation import (
    GenerationCallbacks,
    GenerationPreparationResult,
    GenerationService,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
    QueuedGenerationPreparationJob,
    WorkspaceGenerationController,
)


from tests.presentation.shell.generation.controller.support import (
    _FakeGenerationService,
    _FakeGenerationQueueService,
    _FakePreparationExecutor,
    _BindingRecorder,
    _build_bindings,
    _snapshot,
)


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
