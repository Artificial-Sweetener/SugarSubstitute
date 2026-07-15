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

"""Build listener-scoped binary websocket routing collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerStartRequest,
)
from substitute.infrastructure.comfy.binary_websocket_event_router import (
    BinaryWebsocketEventRouter,
    BinaryWebsocketRoutingCallbacks,
    BinaryWebsocketRoutingContext,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.listener_preview_emitter import (
    ListenerPreviewEmitter,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)


@dataclass(frozen=True)
class ListenerBinaryEventRuntime:
    """Carry binary websocket routing collaborators for one listener run."""

    binary_event_router: BinaryWebsocketEventRouter


def build_listener_binary_event_runtime(
    *,
    request: ListenerStartRequest,
    callbacks: ListenerCallbacks,
    visual_event_guard: ListenerVisualEventGuard,
    decode_preview_image: Callable[[bytes], object],
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None],
    on_visual_diagnostic: Callable[[VisualEventRejectionDiagnostic], None],
) -> ListenerBinaryEventRuntime:
    """Build preview emission and binary websocket routing for one listener run."""

    binary_context = BinaryEventContext(
        workflow_id=request.workflow_id,
        prompt_id=request.prompt_id,
        generation_run_id=request.generation_run_id,
    )
    preview_emitter = ListenerPreviewEmitter(
        binary_context=binary_context,
        visual_event_guard=visual_event_guard,
        decode_preview_image=decode_preview_image,
        on_preview=callbacks.on_preview,
        on_binary_diagnostic=on_binary_diagnostic,
        on_visual_diagnostic=on_visual_diagnostic,
    )
    preview_context = visual_event_guard.context(event_type="preview")
    binary_event_router = BinaryWebsocketEventRouter(
        context=BinaryWebsocketRoutingContext(
            active_prompt_id=request.prompt_id,
            binary_context=binary_context,
            visual_context=preview_context,
            request_identity=visual_event_guard.request_identity(),
        ),
        callbacks=BinaryWebsocketRoutingCallbacks(
            on_emit_preview=preview_emitter.emit,
            on_binary_diagnostic=on_binary_diagnostic,
            on_visual_diagnostic=on_visual_diagnostic,
        ),
    )
    return ListenerBinaryEventRuntime(binary_event_router=binary_event_router)


__all__ = [
    "ListenerBinaryEventRuntime",
    "build_listener_binary_event_runtime",
]
