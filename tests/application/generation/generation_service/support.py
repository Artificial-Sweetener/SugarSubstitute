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

"""Provide typed generation-service test collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from substitute.application.generation import (
    ComfyAssetStagingResult,
    GenerationCallbacks,
    GenerationFailure,
    GenerationService,
)
from substitute.application.ports.comfy_gateway import ComfyGateway
from substitute.application.recipes.recipe_io_service import (
    RecipeIoService,
    WorkflowLike,
)
from substitute.application.recipes.workflow_export_service import WorkflowExportService
from substitute.application.ports import (
    InterruptResult,
    ListenerCallbacks,
    ListenerHandle,
    ListenerSessionConnectRequest,
    ListenerSessionConnectResult,
    ListenerSessionHandle,
    ListenerStartRequest,
    ListenerStartResult,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
    QueueVisualRunContext,
    QueuePromptResult,
)


_RealGenerationService = GenerationService


@dataclass
class _CallbackRecorder:
    """Collect callback invocations for deterministic assertions."""

    cleared: list[str]
    outputs: list[OutputImageUpdate]
    previews: list[PreviewImageUpdate]
    progress: list[ProgressUpdate]
    failures: list[GenerationFailure]
    run_started: list[object]


class _FakeRecipeIoService:
    """Provide deterministic recipe serialization for generation service tests."""

    def __init__(self) -> None:
        """Initialize call capture for serialization assertions."""

        self.calls: list[dict[str, object]] = []

    def serialize_workflow_to_sugar_script(
        self,
        _workflow: object,
        *,
        enabled_node_keys_by_alias: object | None = None,
        disabled_node_keys_by_alias: object | None = None,
    ) -> str:
        """Return deterministic recipe text while recording disabled-node input."""

        self.calls.append(
            {
                "enabled_node_keys_by_alias": enabled_node_keys_by_alias,
                "disabled_node_keys_by_alias": disabled_node_keys_by_alias,
            }
        )
        return 'use "cube" as A'


class _FakeWorkflowExportService:
    """Provide deterministic workflow payload compilation behavior."""

    def __init__(self, workflow_payload: dict[str, Any]) -> None:
        self.workflow_payload = workflow_payload
        self.calls: list[dict[str, Any]] = []

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
        workflow: object | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "sugar_script_text": sugar_script_text,
                "output_dir": output_dir,
                "workflow": workflow,
            }
        )
        return self.workflow_payload


class _FakeGateway:
    """Provide queue/listener/interrupt behavior with deterministic recording."""

    def __init__(
        self,
        *,
        queue_results: list[QueuePromptResult],
        listener_start_results: list[ListenerStartResult] | None = None,
        interrupt_result: InterruptResult | None = None,
    ) -> None:
        self.queue_results = list(queue_results)
        self.listener_start_results = list(listener_start_results or [])
        self.interrupt_result = interrupt_result or InterruptResult(
            status="sent",
            status_code=200,
            error=None,
        )
        self.queue_calls: list[
            tuple[
                dict[str, Any],
                str,
                tuple[str, ...] | None,
                str | None,
                str | None,
                QueueVisualRunContext | None,
            ]
        ] = []
        self.connect_calls: list[ListenerSessionConnectRequest] = []
        self.closed_sessions: list[ListenerSessionHandle] = []
        self.listener_requests: list[ListenerStartRequest] = []
        self.listener_callbacks: list[ListenerCallbacks] = []
        self.call_order: list[str] = []

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        self.connect_calls.append(request)
        self.call_order.append("connect")
        return ListenerSessionConnectResult(
            connected=True,
            handle=ListenerSessionHandle(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                session=SimpleNamespace(),
            ),
            error=None,
        )

    def queue_prompt(
        self,
        workflow_payload: dict[str, Any],
        *,
        client_id: str,
        execution_targets: tuple[str, ...] | None = None,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        self.call_order.append("queue")
        self.queue_calls.append(
            (
                workflow_payload,
                client_id,
                execution_targets,
                preview_method,
                sugar_script,
                visual_context,
            )
        )
        if self.queue_results:
            return self.queue_results.pop(0)
        return QueuePromptResult(
            status="missing_prompt_id",
            prompt_id=None,
            payload=None,
            error=None,
        )

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        self.call_order.append("start")
        self.listener_requests.append(request)
        self.listener_callbacks.append(callbacks)
        if self.listener_start_results:
            return self.listener_start_results.pop(0)
        handle = ListenerHandle(
            prompt_id=request.prompt_id,
            generation_run_id=request.generation_run_id,
            client_id=request.client_id,
            workflow_id=request.workflow_id,
            task=SimpleNamespace(),
        )
        return ListenerStartResult(started=True, handle=handle, error=None)

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        self.call_order.append("close")
        self.closed_sessions.append(handle)

    def interrupt(self) -> InterruptResult:
        return self.interrupt_result


class _FakeAssetStagingService:
    """Provide deterministic generation asset staging behavior."""

    def __init__(self, result: ComfyAssetStagingResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def stage_payload(
        self,
        *,
        workflow_payload: dict[str, object],
        workflow_id: str,
        workflow_name: str,
        workflow: object | None = None,
    ) -> ComfyAssetStagingResult:
        self.calls.append(
            {
                "workflow_payload": workflow_payload,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "workflow": workflow,
            }
        )
        return self.result


def _build_generation_callbacks(recorder: _CallbackRecorder) -> GenerationCallbacks:
    """Create callback wiring that appends events into recorder lists."""
    return GenerationCallbacks(
        randomize_seeds=lambda: None,
        on_run_started=lambda event: recorder.run_started.append(event),
        on_progress=lambda event: recorder.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: recorder.previews.append(event),
        on_output_image=lambda event: recorder.outputs.append(event),
        on_failure=lambda failure: recorder.failures.append(failure),
        on_timing=lambda _event: None,
    )


def _as_json_object(payload: dict[str, Any]) -> dict[str, object]:
    """Adapt a test literal to the application's JSON-object boundary."""

    return cast(dict[str, object], payload)


def _build_generation_service(
    *,
    recipe_io_service: _FakeRecipeIoService,
    workflow_export_service: _FakeWorkflowExportService,
    comfy_gateway: _FakeGateway,
    **dependencies: object,
) -> GenerationService:
    """Build the real service with fake external boundaries for one contract."""

    return _RealGenerationService(
        recipe_io_service=cast(RecipeIoService, recipe_io_service),
        workflow_export_service=cast(WorkflowExportService, workflow_export_service),
        comfy_gateway=cast(ComfyGateway, comfy_gateway),
        **cast(Any, dependencies),
    )


def _build_workflow() -> WorkflowLike:
    """Create minimal workflow state required by generation request."""
    return cast(
        WorkflowLike,
        SimpleNamespace(stack_order=["A"], cubes={}, global_overrides={}),
    )
