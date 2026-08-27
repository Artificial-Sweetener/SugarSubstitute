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

"""Test generation queue failure reporting and callbacks."""

from __future__ import annotations

from __future__ import annotations
from substitute.application.errors import ErrorReport, ErrorReportKind
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


def test_run_single_generation_queue_failure_calls_failure_callback() -> None:
    """Missing prompt id should fail queue stage and skip listener startup."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="missing_prompt_id",
                prompt_id=None,
                payload={"status": "ok"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
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
    assert result.failure.stage == "queue"
    assert result.failure.message == "queue_prompt did not return prompt_id"
    assert recorder.cleared == []
    assert len(recorder.failures) == 1
    assert fake_gateway.listener_requests == []
    assert fake_gateway.call_order == ["connect", "queue", "close"]
    assert len(fake_gateway.closed_sessions) == 1


def test_run_single_generation_queue_failure_uses_gateway_error() -> None:
    """Missing prompt id should preserve gateway error detail when present."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="missing_prompt_id",
                prompt_id=None,
                payload={"status": "error"},
                error="HTTP 500 from /prompt",
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
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

    assert result.failure is not None
    assert result.failure.message == "HTTP 500 from /prompt"
    assert recorder.failures[0] == result.failure
    assert fake_gateway.call_order == ["connect", "queue", "close"]


def test_run_single_generation_queue_failure_preserves_error_report() -> None:
    """Queue failures should carry structured reports into generation failures."""

    report = ErrorReport(
        kind=ErrorReportKind.PROMPT_VALIDATION,
        title="Prompt validation failed",
        message="Invalid prompt",
        stage="queue",
    )
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="error",
                prompt_id=None,
                payload={"error": "bad"},
                error="Invalid prompt",
                error_report=report,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
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

    assert result.failure is not None
    assert result.failure.error_report is report
    assert recorder.failures[0] == result.failure
    assert fake_gateway.call_order == ["connect", "queue", "close"]
