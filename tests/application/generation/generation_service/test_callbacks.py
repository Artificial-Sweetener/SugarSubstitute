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

"""Test durable and visual generation callback routing."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from substitute.application.generation import (
    GenerationRequest,
)
from substitute.application.ports import (
    OutputImageUpdate,
    PreviewImageUpdate,
    QueuePromptResult,
)

from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _build_generation_callbacks,
    _as_json_object,
    _build_generation_service,
    _build_workflow,
)


def test_output_callback_preserves_origin_workflow_id_after_listener_emit() -> None:
    """Output callback payload should retain origin workflow id from start request."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    payload = {"N1": {"class_type": "KSampler"}}
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(payload),
        comfy_gateway=fake_gateway,
    )

    service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-origin",
            workflow_name="Workflow Origin",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )
    listener_request = fake_gateway.listener_requests[0]
    fake_gateway.listener_callbacks[0].on_output_image(
        OutputImageUpdate(
            workflow_id="wf-origin",
            workflow_payload=_as_json_object(payload),
            file_path=Path("output.png"),
            node_id="N1",
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )

    assert recorder.cleared == []
    assert len(recorder.outputs) == 1
    assert recorder.outputs[0].workflow_id == "wf-origin"
    assert recorder.outputs[0].node_id == "N1"


def test_visual_callbacks_forward_without_clearing_durable_output() -> None:
    """Listener visuals should leave replacement to successful image commit."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    payload = {"N1": {"class_type": "KSampler"}}
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(payload),
        comfy_gateway=fake_gateway,
    )

    service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-origin",
            workflow_name="Workflow Origin",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )
    listener_request = fake_gateway.listener_requests[0]

    fake_gateway.listener_callbacks[0].on_preview(
        PreviewImageUpdate(workflow_id="wf-other", image=object())
    )
    fake_gateway.listener_callbacks[0].on_preview(
        PreviewImageUpdate(
            workflow_id="wf-origin",
            image=object(),
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )
    fake_gateway.listener_callbacks[0].on_output_image(
        OutputImageUpdate(
            workflow_id="wf-origin",
            workflow_payload=_as_json_object(payload),
            file_path=Path("output.png"),
            node_id="N1",
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )

    assert recorder.cleared == []
    assert [event.workflow_id for event in recorder.previews] == [
        "wf-other",
        "wf-origin",
    ]
    assert len(recorder.outputs) == 1
