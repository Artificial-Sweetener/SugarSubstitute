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

"""Execute a composed Comfy websocket listener runtime."""

from __future__ import annotations

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerStartRequest,
)
from substitute.infrastructure.comfy.comfy_execution_timing import (
    ComfyExecutionTimingEmitter,
)
from substitute.infrastructure.comfy.listener_event_runtime import (
    build_listener_event_runtime,
)
from substitute.infrastructure.comfy.listener_runtime_composition import (
    ListenerRuntimeComposition,
)
from substitute.infrastructure.comfy.listener_websocket_connection import (
    ListenerWebsocketSession,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ComfyWebsocketListenerEngine,
)


def run_listener_runtime(
    *,
    request: ListenerStartRequest,
    callbacks: ListenerCallbacks,
    runtime: ListenerRuntimeComposition,
) -> None:
    """Run one composed listener runtime and dispatch terminal callbacks."""

    websocket_session: ListenerWebsocketSession | None = None
    timing_emitter: ComfyExecutionTimingEmitter | None = None
    try:
        websocket_session = runtime.websocket_connection_manager.open()
        event_runtime = build_listener_event_runtime(
            request=request,
            callbacks=callbacks,
            endpoint=runtime.endpoint,
            progress_context=runtime.progress_context,
            source_identity_resolver=runtime.output_source_resolver.resolve,
            source_metadata_resolver=(
                runtime.model_load_source_metadata_resolver.resolve
            ),
            cube_output_handler=runtime.cube_output_handler,
        )
        timing_emitter = event_runtime.timing_emitter

        engine_result = ComfyWebsocketListenerEngine(
            websocket_client=websocket_session.websocket_client,
            receive_timeout_seconds=runtime.receive_timeout_seconds,
            active_prompt_id=request.prompt_id,
            prompt_liveness_probe=runtime.prompt_liveness_probe,
            all_node_ids=event_runtime.all_node_ids,
            json_event_router=event_runtime.json_event_router,
            binary_event_router=runtime.binary_event_router,
            callbacks=event_runtime.engine_callbacks,
        ).run()
        if engine_result.prompt_finished:
            timing_emitter.emit_once(count_active_nodes=True)
    except Exception as error:
        runtime.callback_dispatcher.emit_failure(
            error,
            timing_emitter=timing_emitter,
        )
    finally:
        if websocket_session is not None:
            websocket_session.close()
        runtime.callback_dispatcher.emit_completed()


__all__ = ["run_listener_runtime"]
