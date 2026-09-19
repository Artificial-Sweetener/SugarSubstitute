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
    GenerationRequest,
    GenerationService,
)
from substitute.application.errors import ErrorReportKind
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationPreflightError,
    GenerationUiBindings,
    WorkspaceGenerationController,
)


from tests.presentation.shell.generation.controller.support import (
    _FakeGenerationService,
    _FakeGenerationQueueService,
    _BindingRecorder,
    _build_bindings,
    _snapshot,
    _without_output_sessions,
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
    assert _without_output_sessions(
        [
            cast(GenerationJobSnapshot, call["snapshot"])
            for call in fake_queue.enqueue_calls
        ]
    ) == [_snapshot("Before failure")]
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
