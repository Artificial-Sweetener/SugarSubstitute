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

"""Own generation queue dispatch and listener lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sugarsubstitute_shared.localization import app_text

from substitute.application.generation.generation_models import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationStartResult,
    PreparedGenerationRequest,
    generation_failure_from_listener,
)
from substitute.application.generation.generation_run_started_notifier import (
    notify_generation_run_started,
)
from substitute.application.generation.native_visual_run_context import (
    attach_native_visual_sources,
)
from substitute.application.generation.native_cube_presentation import (
    native_cube_presentation_labels,
)
from substitute.application.generation.preview_preference_service import (
    GenerationPreviewMethodResolver,
)
from substitute.application.generation.visual_run_context_builder import (
    VisualRunContextBuilder,
)
from substitute.application.ports.comfy_gateway import (
    ComfyGateway,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerHandle,
    ListenerOutputSource,
    ListenerSessionHandle,
    ListenerSessionConnectRequest,
    ListenerStartRequest,
    OutputSavePlan,
    QueueVisualRunContext,
)
from substitute.domain.common import WorkflowId
from substitute.application.workflows.input_asset_diagnostics import (
    log_generation_payload_assets,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_warning,
)

_LOGGER = get_logger("application.generation.generation_execution_dispatcher")


class ModelUsageRecorder(Protocol):
    """Record model identities after a generation is accepted by ComfyUI."""

    def record_queued_payload(self, workflow_payload: Mapping[str, object]) -> int:
        """Record exact referenced models and return their count."""


class GenerationExecutionDispatcher:
    """Queue prepared prompts and own their websocket listener lifecycles."""

    def __init__(
        self,
        *,
        comfy_gateway: ComfyGateway,
        preview_method_resolver: GenerationPreviewMethodResolver,
        visual_run_context_builder: VisualRunContextBuilder,
        output_dir: Path,
        client_id: str,
        model_usage_recorder: ModelUsageRecorder | None = None,
    ) -> None:
        """Bind queue, output, and listener collaborators."""

        self._comfy_gateway = comfy_gateway
        self._preview_method_resolver = preview_method_resolver
        self._visual_run_context_builder = visual_run_context_builder
        self._output_dir = output_dir
        self._client_id = client_id
        self._model_usage_recorder = model_usage_recorder
        self._active_listener_handles: list[ListenerHandle] = []

    @property
    def active_listener_handles(self) -> tuple[ListenerHandle, ...]:
        """Return a snapshot of currently tracked listener handles."""

        return tuple(self._active_listener_handles)

    def dispatch(
        self,
        *,
        request: PreparedGenerationRequest,
        workflow_payload: dict[str, object],
        output_save_plan: OutputSavePlan,
        callbacks: GenerationCallbacks,
        native_cube_execution: bool,
        execution_targets: tuple[str, ...] | None = None,
        standard_output_sources: tuple[ListenerOutputSource, ...] = (),
    ) -> GenerationStartResult:
        """Queue one prepared payload and start its connected listener."""

        generation_run_id = uuid4().hex
        run_client_id = self._client_id_for_run(generation_run_id)
        listener_session_result = self._comfy_gateway.connect_listener_session(
            ListenerSessionConnectRequest(
                workflow_id=request.workflow_id,
                generation_run_id=generation_run_id,
                client_id=run_client_id,
            )
        )
        if (
            not listener_session_result.connected
            or listener_session_result.handle is None
        ):
            log_warning(
                _LOGGER,
                "Failed to connect generation listener session before queueing",
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                generation_run_id=generation_run_id,
                client_id=run_client_id,
                error=listener_session_result.error,
            )
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="listen",
                    workflow_id=request.workflow_id,
                    generation_run_id=generation_run_id,
                    client_id=run_client_id,
                    message=listener_session_result.error
                    or app_text("Failed to connect generation listener session"),
                ),
            )
        listener_session = listener_session_result.handle
        visual_context = self._visual_context(
            request=request,
            workflow_payload=workflow_payload,
            generation_run_id=generation_run_id,
            run_client_id=run_client_id,
            native_cube_execution=native_cube_execution,
            standard_output_sources=standard_output_sources,
        )
        if native_cube_execution:
            queue_result = self._comfy_gateway.queue_cube_workflow(
                workflow_payload,
                client_id=run_client_id,
                preview_method=self._preview_method_resolver.resolved_comfy_preview_method(),
                visual_context=visual_context,
                persistence_sugar_script=request.persistence_sugar_script,
            )
        else:
            queue_result = self._comfy_gateway.queue_prompt(
                workflow_payload,
                client_id=run_client_id,
                execution_targets=execution_targets,
                preview_method=self._preview_method_resolver.resolved_comfy_preview_method(),
                visual_context=visual_context,
            )
        prompt_id = queue_result.prompt_id
        if prompt_id is None:
            self._comfy_gateway.close_listener_session(listener_session)
            log_warning(
                _LOGGER,
                "queue_prompt did not return prompt_id",
                workflow_id=request.workflow_id,
                generation_run_id=generation_run_id,
                client_id=run_client_id,
                queue_status=queue_result.status,
                queue_error=queue_result.error,
                queue_payload=queue_result.payload,
            )
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="queue",
                    workflow_id=request.workflow_id,
                    generation_run_id=generation_run_id,
                    client_id=run_client_id,
                    message=queue_result.error
                    or app_text("queue_prompt did not return prompt_id"),
                    error_report=queue_result.error_report,
                ),
            )
        if native_cube_execution:
            standard_output_sources = queue_result.output_sources
        execution_node_sources = (
            queue_result.execution_sources if native_cube_execution else ()
        )
        if native_cube_execution:
            visual_context = attach_native_visual_sources(
                visual_context,
                output_sources=standard_output_sources,
                execution_sources=execution_node_sources,
            )
        execution_prompt_payload = (
            queue_result.execution_prompt if native_cube_execution else None
        )
        queued_payload = execution_prompt_payload or workflow_payload
        self._record_queued_models(
            workflow_payload=queued_payload,
            workflow_id=request.workflow_id,
            prompt_id=prompt_id,
        )
        log_generation_payload_assets(
            queued_payload,
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
            stage="queued",
        )
        return self._start_listener(
            request=request,
            workflow_payload=workflow_payload,
            output_save_plan=output_save_plan,
            callbacks=callbacks,
            prompt_id=prompt_id,
            generation_run_id=generation_run_id,
            run_client_id=run_client_id,
            listener_session=listener_session,
            visual_context=visual_context,
            standard_output_sources=standard_output_sources,
            execution_prompt_payload=execution_prompt_payload,
            execution_node_sources=execution_node_sources,
        )

    def _visual_context(
        self,
        *,
        request: PreparedGenerationRequest,
        workflow_payload: dict[str, object],
        generation_run_id: str,
        run_client_id: str,
        native_cube_execution: bool,
        standard_output_sources: tuple[ListenerOutputSource, ...],
    ) -> QueueVisualRunContext:
        """Build native or ordinary output-routing context for one run."""

        if native_cube_execution:
            return QueueVisualRunContext(
                workflow_id=request.workflow_id,
                generation_run_id=generation_run_id,
                client_id=run_client_id,
                output_session_id=request.output_session_id,
                scene_run_id=request.scene_run_id,
                scene_key=request.scene_key,
                scene_title=request.scene_title,
                scene_order=request.scene_order,
                scene_count=request.scene_count,
                sources={},
                cube_presentations=native_cube_presentation_labels(request.workflow),
            )
        return self._visual_run_context_builder.build(
            workflow_payload=workflow_payload,
            workflow_id=request.workflow_id,
            generation_run_id=generation_run_id,
            client_id=run_client_id,
            output_session_id=request.output_session_id,
            scene_run_id=request.scene_run_id,
            scene_key=request.scene_key,
            scene_title=request.scene_title,
            scene_order=request.scene_order,
            scene_count=request.scene_count,
            explicit_sources=standard_output_sources,
        )

    def _record_queued_models(
        self,
        *,
        workflow_payload: Mapping[str, object],
        workflow_id: WorkflowId,
        prompt_id: str,
    ) -> None:
        """Record queued models without failing an accepted generation."""

        if self._model_usage_recorder is None:
            return
        try:
            self._model_usage_recorder.record_queued_payload(workflow_payload)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Failed to record queued generation model usage",
                workflow_id=workflow_id,
                prompt_id=prompt_id,
                error=error,
            )

    def _start_listener(
        self,
        *,
        request: PreparedGenerationRequest,
        workflow_payload: dict[str, object],
        output_save_plan: OutputSavePlan,
        callbacks: GenerationCallbacks,
        prompt_id: str,
        generation_run_id: str,
        run_client_id: str,
        listener_session: ListenerSessionHandle,
        visual_context: QueueVisualRunContext,
        standard_output_sources: tuple[ListenerOutputSource, ...],
        execution_prompt_payload: dict[str, object] | None,
        execution_node_sources: tuple[ListenerOutputSource, ...],
    ) -> GenerationStartResult:
        """Start and track the listener for an accepted prompt."""

        handle_box: dict[str, ListenerHandle | None] = {"value": None}

        def on_listener_failed(event: ListenerFailure) -> None:
            callbacks.on_failure(
                generation_failure_from_listener(event, client_id=run_client_id)
            )

        def on_listener_completed(event: ListenerCompleted) -> None:
            handle = handle_box["value"]
            if handle is not None:
                try:
                    self._active_listener_handles.remove(handle)
                except ValueError:
                    pass
            if callbacks.on_completed is not None:
                callbacks.on_completed(event)

        listener_callbacks = ListenerCallbacks(
            on_progress=callbacks.on_progress,
            on_model_load_progress=callbacks.on_model_load_progress,
            on_preview=callbacks.on_preview,
            on_output_image=callbacks.on_output_image,
            on_failed=on_listener_failed,
            on_timing=callbacks.on_timing,
            on_completed=on_listener_completed,
        )
        notify_generation_run_started(
            callbacks.on_run_started,
            workflow_id=request.workflow_id,
            generation_run_id=generation_run_id,
            output_session_id=(
                request.output_session_id or request.scene_run_id or generation_run_id
            ),
            prompt_id=prompt_id,
            client_id=run_client_id,
            visual_context=visual_context,
        )
        listener_result = self._comfy_gateway.start_listener(
            request=ListenerStartRequest(
                prompt_id=prompt_id,
                generation_run_id=generation_run_id,
                client_id=run_client_id,
                listener_session=listener_session,
                output_dir=self._output_dir,
                workflow_payload=workflow_payload,
                persistence_sugar_script=request.persistence_sugar_script,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                output_run_number=request.output_run_number,
                output_save_plan=output_save_plan,
                output_session_id=request.output_session_id,
                scene_run_id=request.scene_run_id,
                scene_key=request.scene_key,
                scene_title=request.scene_title,
                scene_order=request.scene_order,
                scene_count=request.scene_count,
                standard_output_sources=standard_output_sources,
                execution_prompt_payload=execution_prompt_payload,
                execution_node_sources=execution_node_sources,
            ),
            callbacks=listener_callbacks,
        )
        if not listener_result.started or listener_result.handle is None:
            self._comfy_gateway.close_listener_session(listener_session)
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="listen",
                    workflow_id=request.workflow_id,
                    generation_run_id=generation_run_id,
                    prompt_id=prompt_id,
                    client_id=run_client_id,
                    message=listener_result.error
                    or app_text("Failed to start generation listener"),
                ),
            )
        handle_box["value"] = listener_result.handle
        self._active_listener_handles.append(listener_result.handle)
        return GenerationStartResult(
            started=True,
            prompt_id=prompt_id,
            failure=None,
            generation_run_id=generation_run_id,
            client_id=run_client_id,
        )

    def _client_id_for_run(self, generation_run_id: str) -> str:
        """Return the shared websocket and queue client id for one run."""

        return f"{self._client_id}:{generation_run_id}"

    @staticmethod
    def _notify_failure(
        *,
        callbacks: GenerationCallbacks,
        failure: GenerationFailure,
    ) -> GenerationStartResult:
        """Emit one failed-start callback and normalized result."""

        callbacks.on_failure(failure)
        return GenerationStartResult(
            started=False,
            prompt_id=failure.prompt_id,
            failure=failure,
            generation_run_id=failure.generation_run_id,
            client_id=failure.client_id,
        )


__all__ = ["GenerationExecutionDispatcher", "ModelUsageRecorder"]
