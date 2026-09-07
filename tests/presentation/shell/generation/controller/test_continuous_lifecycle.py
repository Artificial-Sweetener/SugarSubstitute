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

from pathlib import Path
from typing import Any, cast

from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationService,
)
from substitute.application.ports import (
    OutputImageUpdate,
    PreviewImageUpdate,
)
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
    _progress_update,
    _completed,
    _emit_completed,
    _bindings_with_snapshots,
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

    _emit_completed(first_callbacks, _completed("wf-1"))

    assert controller.is_continuous_active is True
    assert recorder.completed == [_completed("wf-1")]
    assert _without_output_sessions(
        [
            cast(GenerationJobSnapshot, call["snapshot"])
            for call in fake_queue.enqueue_calls
        ]
    ) == [
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

    _emit_completed(first_callbacks, _completed("wf-1"))
    assert _without_output_sessions(
        [
            cast(GenerationJobSnapshot, call["snapshot"])
            for call in fake_queue.enqueue_calls
        ]
    ) == [
        first_scene,
        second_scene,
    ]

    _emit_completed(second_callbacks, _completed("wf-1"))

    assert len(fake_queue.batch_entry_calls) == 2
    assert _without_output_sessions(
        [
            cast(GenerationJobSnapshot, call["snapshot"])
            for call in fake_queue.enqueue_calls
        ]
    ) == [
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

    _emit_completed(callbacks, _completed("wf-1"))

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

    _emit_completed(callbacks, _completed("wf-1"))

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
    _emit_completed(callbacks, _completed("wf-1"))

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

    assert recorder.clear_output_calls == []
    assert recorder.progress == [
        _progress_update(workflow_percent=50.0, sampler_percent=25.0)
    ]
    assert len(recorder.previews) == 1
    assert len(recorder.outputs) == 1
    assert len(recorder.failures) == 1
