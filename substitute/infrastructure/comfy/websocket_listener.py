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

"""Listen for Comfy websocket events and dispatch typed generation callbacks."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.ports.comfy_gateway import (
    CubeExecutionTiming,
    GenerationExecutionTiming,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerSessionHandle,
    ListenerStartRequest,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    OutputSavePlan,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.listener_runtime_composition import (
    ListenerRuntimeComposition,
    build_listener_runtime_composition,
)
from substitute.infrastructure.comfy.listener_run_loop import run_listener_runtime
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
)
from substitute.infrastructure.comfy.preview_image_decoder import (
    decode_preview_image,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("infrastructure.comfy.websocket_listener")


class ComfyWebsocketListener:
    """Await Comfy websocket prompt completion and dispatch progress/image callbacks."""

    def __init__(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
        *,
        websocket_url: str | None = None,
        endpoint: ComfyEndpoint | None = None,
        preconnected_session: PreconnectedComfyWebsocketSession | None = None,
        connect_timeout_seconds: float = 10.0,
        receive_timeout_seconds: float = 60.0,
        preview_image_decoder: Callable[[bytes], object] | None = None,
    ) -> None:
        """Initialize listener with immutable request payload and callback wiring."""
        self._request = request
        self._callbacks = callbacks
        self._preview_image_decoder = preview_image_decoder or decode_preview_image
        self._runtime_composition: ListenerRuntimeComposition = (
            build_listener_runtime_composition(
                request=request,
                callbacks=callbacks,
                logger=_LOGGER,
                decode_preview_image=self._preview_image_decoder,
                websocket_url=websocket_url,
                endpoint=endpoint,
                preconnected_session=preconnected_session,
                connect_timeout_seconds=connect_timeout_seconds,
                receive_timeout_seconds=receive_timeout_seconds,
            )
        )
        self.cube_output_node_ids = self._runtime_composition.cube_output_node_ids

    def run(self) -> None:
        """Process websocket events until prompt completion or listener failure."""
        run_listener_runtime(
            request=self._request,
            callbacks=self._callbacks,
            runtime=self._runtime_composition,
        )


__all__ = [
    "ComfyWebsocketListener",
    "CubeExecutionTiming",
    "GenerationExecutionTiming",
    "ListenerCallbacks",
    "ListenerCompleted",
    "ListenerFailure",
    "ListenerSessionHandle",
    "ModelLoadProgressUpdate",
    "ListenerStartRequest",
    "OutputImageUpdate",
    "OutputSavePlan",
    "PreconnectedComfyWebsocketSession",
    "PreviewImageUpdate",
    "ProgressUpdate",
]
