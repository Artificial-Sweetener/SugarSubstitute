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

"""Test unresolved UUID graph validation before dispatch."""

from __future__ import annotations

from __future__ import annotations
from substitute.application.generation import (
    GenerationRequest,
)
from substitute.application.ports import (
    QueuePromptResult,
)

from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _build_generation_callbacks,
    _build_generation_service,
    _build_workflow,
)


def test_run_single_generation_rejects_unresolved_uuid_wrapper_nodes() -> None:
    """UUID wrapper class_type values should fail build stage before queueing."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-ignored",
                payload={"prompt_id": "pid-ignored"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"1": {"class_type": "94f725d5-39bf-4060-be68-f573214a2055"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "build"
    assert len(recorder.failures) == 1
    assert fake_gateway.queue_calls == []


def test_run_single_generation_rejects_wrapped_unresolved_uuid_nodes() -> None:
    """UUID wrapper validation should inspect wrapped executable prompt nodes."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-ignored",
                payload={"prompt_id": "pid-ignored"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {
                "prompt": {"1": {"class_type": "94f725d5-39bf-4060-be68-f573214a2055"}},
                "workflow": {"nodes": []},
            }
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "build"
    assert fake_gateway.queue_calls == []
