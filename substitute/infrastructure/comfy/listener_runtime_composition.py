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

"""Compose listener-scoped Comfy websocket runtime collaborators."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerStartRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.binary_websocket_event_router import (
    BinaryWebsocketEventRouter,
)
from substitute.infrastructure.comfy.cube_output_event_handler import (
    CubeOutputEventHandler,
)
from substitute.infrastructure.comfy.standard_executed_image_handler import (
    StandardExecutedImageHandler,
)
from substitute.infrastructure.comfy.listener_binary_event_runtime import (
    build_listener_binary_event_runtime,
)
from substitute.infrastructure.comfy.listener_callback_dispatcher import (
    ListenerCallbackDispatcher,
)
from substitute.infrastructure.comfy.listener_diagnostic_logging import (
    ListenerDiagnosticLogger,
)
from substitute.infrastructure.comfy.listener_model_load_source_metadata import (
    ListenerModelLoadSourceMetadataResolver,
)
from substitute.infrastructure.comfy.listener_output_pipeline import (
    build_listener_output_pipeline,
)
from substitute.infrastructure.comfy.listener_output_source_resolver import (
    ListenerOutputSourceResolver,
)
from substitute.infrastructure.comfy.listener_progress_emitter import (
    ListenerProgressContext,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.listener_websocket_connection import (
    ListenerWebsocketConnectionManager,
)
from substitute.infrastructure.comfy.prompt_liveness import (
    ComfyPromptLivenessProbe,
    PromptLivenessProbe,
)
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
    is_disconnect_error,
)


@dataclass(frozen=True)
class ListenerRuntimeComposition:
    """Carry collaborators needed by the listener facade and run loop."""

    endpoint: ComfyEndpoint
    receive_timeout_seconds: float
    prompt_liveness_probe: PromptLivenessProbe
    websocket_connection_manager: ListenerWebsocketConnectionManager
    callback_dispatcher: ListenerCallbackDispatcher
    progress_context: ListenerProgressContext
    output_source_resolver: ListenerOutputSourceResolver
    cube_output_handler: CubeOutputEventHandler
    standard_output_handler: StandardExecutedImageHandler
    model_load_source_metadata_resolver: ListenerModelLoadSourceMetadataResolver
    binary_event_router: BinaryWebsocketEventRouter
    cube_output_node_ids: set[str]


def build_listener_runtime_composition(
    *,
    request: ListenerStartRequest,
    callbacks: ListenerCallbacks,
    logger: logging.Logger,
    decode_preview_image: Callable[[bytes], object],
    websocket_url: str | None,
    endpoint: ComfyEndpoint | None,
    preconnected_session: PreconnectedComfyWebsocketSession | None,
    connect_timeout_seconds: float,
    receive_timeout_seconds: float,
) -> ListenerRuntimeComposition:
    """Build all listener-scoped collaborators used outside the event loop."""

    diagnostics = ListenerDiagnosticLogger(logger)
    callback_dispatcher = ListenerCallbackDispatcher(
        request=request,
        callbacks=callbacks,
        is_disconnect_error=is_disconnect_error,
    )
    progress_context = ListenerProgressContext(
        workflow_id=request.workflow_id,
        generation_run_id=request.generation_run_id,
        prompt_id=request.prompt_id,
        client_id=request.client_id,
    )
    visual_event_guard = ListenerVisualEventGuard(
        workflow_id=request.workflow_id,
        generation_run_id=request.generation_run_id,
        prompt_id=request.prompt_id,
        client_id=request.client_id,
        on_diagnostic=diagnostics.visual_event,
    )
    resolved_endpoint = endpoint or ComfyEndpoint(host="127.0.0.1", port=8188)
    resolved_websocket_url = websocket_url or ComfyEndpoint(
        host=resolved_endpoint.host,
        port=resolved_endpoint.port,
    ).websocket_url(request.client_id)
    websocket_connection_manager = ListenerWebsocketConnectionManager(
        client_id=request.client_id,
        websocket_url=resolved_websocket_url,
        workflow_id=request.workflow_id,
        generation_run_id=request.generation_run_id,
        prompt_id=request.prompt_id,
        connect_timeout_seconds=connect_timeout_seconds,
        preconnected_session=preconnected_session,
    )
    output_pipeline = build_listener_output_pipeline(
        request=request,
        endpoint=resolved_endpoint,
        callbacks=callbacks,
        visual_event_guard=visual_event_guard,
        on_output_source_diagnostic=diagnostics.output_source,
        on_cube_output_diagnostic=diagnostics.cube_output,
    )
    model_load_source_metadata_resolver = ListenerModelLoadSourceMetadataResolver(
        workflow_payload=request.workflow_payload,
        workflow_id=request.workflow_id,
        prompt_id=request.prompt_id,
        on_diagnostic=diagnostics.model_load_source_metadata,
    )
    binary_event_runtime = build_listener_binary_event_runtime(
        request=request,
        callbacks=callbacks,
        visual_event_guard=visual_event_guard,
        decode_preview_image=decode_preview_image,
        on_binary_diagnostic=diagnostics.binary_event,
        on_visual_diagnostic=diagnostics.visual_event,
    )
    return ListenerRuntimeComposition(
        endpoint=resolved_endpoint,
        receive_timeout_seconds=receive_timeout_seconds,
        prompt_liveness_probe=ComfyPromptLivenessProbe(
            endpoint=resolved_endpoint,
            timeout_seconds=min(receive_timeout_seconds, 5.0),
        ),
        websocket_connection_manager=websocket_connection_manager,
        callback_dispatcher=callback_dispatcher,
        progress_context=progress_context,
        output_source_resolver=output_pipeline.output_source_resolver,
        cube_output_handler=output_pipeline.cube_output_handler,
        standard_output_handler=output_pipeline.standard_output_handler,
        model_load_source_metadata_resolver=model_load_source_metadata_resolver,
        binary_event_router=binary_event_runtime.binary_event_router,
        cube_output_node_ids=output_pipeline.cube_output_node_ids,
    )


__all__ = [
    "ListenerRuntimeComposition",
    "build_listener_runtime_composition",
]
