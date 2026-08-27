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
    GenerationRequest,
    GenerationService,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
    WorkspaceGenerationController,
)


from tests.presentation.shell.generation.controller.support import (
    _FakeGenerationService,
    _FakeGenerationQueueService,
    _BindingRecorder,
    _build_bindings,
    _snapshot,
    _bindings_with_snapshots,
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
