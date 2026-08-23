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
    GenerationService,
)
from substitute.application.ports import (
    InterruptResult,
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
