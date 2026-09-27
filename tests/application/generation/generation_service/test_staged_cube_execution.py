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

"""Exercise ordered native Cube prompts through the real generation service."""

from __future__ import annotations

from dataclasses import replace
from collections.abc import Callable

from substitute.application.generation import GenerationRequest
from substitute.application.ports import (
    ListenerCompleted,
    ListenerFailure,
    QueuePromptResult,
)
from substitute.domain.workflow import WorkflowState
from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeGateway,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _build_generation_callbacks,
    _build_generation_service,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def _disconnected_workflow() -> WorkflowState:
    """Place the image before a lexicographically earlier video identity."""

    workflow = graph_backed_cube_workflow("z-image", "a-video")
    document = workflow.direct_workflow
    assert document is not None
    analysis = document.cube_analysis
    assert analysis is not None
    document.cube_analysis = replace(analysis, edges=())
    return workflow


def _queued(prompt_id: str) -> QueuePromptResult:
    """Return an accepted native queue response."""

    return QueuePromptResult(
        status="queued",
        prompt_id=prompt_id,
        payload={"prompt_id": prompt_id},
        error=None,
    )


def test_disconnected_cubes_queue_in_authored_order_after_completion() -> None:
    """A later video cannot start until its earlier image prompt completes."""

    gateway = _FakeGateway(queue_results=[_queued("image"), _queued("video")])
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService({}),
        comfy_gateway=gateway,
    )
    recorder = _CallbackRecorder([], [], [], [], [], [])
    deferred_advances: list[Callable[[], None]] = []
    completions: list[ListenerCompleted] = []
    callbacks = replace(
        _build_generation_callbacks(recorder),
        request_stage_advance=deferred_advances.append,
        on_completed=completions.append,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf", workflow_name="Mixed", workflow=_disconnected_workflow()
        ),
        callbacks=callbacks,
    )

    assert result.started
    assert result.prompt_id == "image"
    assert len(gateway.queue_calls) == 1
    assert gateway.queue_calls[0][2] == ("z-image",)
    assert len(recorder.run_started) == 1
    gateway.listener_callbacks[0].on_completed(
        ListenerCompleted("wf", result.generation_run_id or "", "image")
    )
    assert len(gateway.queue_calls) == 1
    assert completions == []
    assert len(deferred_advances) == 1
    deferred_advances.pop()()

    assert len(gateway.queue_calls) == 2
    assert gateway.queue_calls[1][2] == ("a-video",)
    assert len(recorder.run_started) == 2
    assert {request.generation_run_id for request in gateway.listener_requests} == {
        result.generation_run_id
    }
    assert {request.client_id for request in gateway.listener_requests} == {
        result.client_id
    }
    assert (
        gateway.listener_requests[0].output_save_plan
        == gateway.listener_requests[1].output_save_plan
    )
    gateway.listener_callbacks[1].on_completed(
        ListenerCompleted("wf", result.generation_run_id or "", "video")
    )
    assert [event.prompt_id for event in completions] == ["video"]


def test_failed_image_stage_does_not_queue_video() -> None:
    """A failed first Cube terminates the user run before later Cubes start."""

    gateway = _FakeGateway(queue_results=[_queued("image"), _queued("video")])
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService({}),
        comfy_gateway=gateway,
    )
    recorder = _CallbackRecorder([], [], [], [], [], [])
    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf", workflow_name="Mixed", workflow=_disconnected_workflow()
        ),
        callbacks=_build_generation_callbacks(recorder),
    )
    gateway.listener_callbacks[0].on_failed(
        ListenerFailure("wf", result.generation_run_id or "", "image", "failed")
    )
    assert len(gateway.queue_calls) == 1
    assert len(recorder.failures) == 1


def test_cancellation_before_advance_does_not_queue_video() -> None:
    """Interrupting a completed first stage cancels pending advancement."""

    gateway = _FakeGateway(queue_results=[_queued("image"), _queued("video")])
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService({}),
        comfy_gateway=gateway,
    )
    recorder = _CallbackRecorder([], [], [], [], [], [])
    deferred_advances: list[Callable[[], None]] = []
    callbacks = replace(
        _build_generation_callbacks(recorder),
        request_stage_advance=deferred_advances.append,
    )
    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf", workflow_name="Mixed", workflow=_disconnected_workflow()
        ),
        callbacks=callbacks,
    )
    gateway.listener_callbacks[0].on_completed(
        ListenerCompleted("wf", result.generation_run_id or "", "image")
    )
    service.interrupt_generation()
    deferred_advances.pop()()
    assert len(gateway.queue_calls) == 1
