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

"""Wire listener preview emission context and callback ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import PreviewImageUpdate
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.preview_emission import (
    PreviewEmissionCallbacks,
    PreviewEmissionRequest,
    emit_preview_image,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)


@dataclass(frozen=True)
class ListenerPreviewEmitter:
    """Emit routed preview requests for a single listener run."""

    binary_context: BinaryEventContext
    visual_event_guard: ListenerVisualEventGuard
    decode_preview_image: Callable[[bytes], object]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None]
    on_visual_diagnostic: Callable[[VisualEventRejectionDiagnostic], None]

    def emit(self, request: PreviewEmissionRequest) -> None:
        """Emit a preview callback from a routed preview emission request."""

        emit_preview_image(
            request,
            binary_context=self.binary_context,
            visual_context=self.visual_event_guard.context(
                event_type="preview",
                node_id=request.node_id,
            ),
            callbacks=PreviewEmissionCallbacks(
                decode_preview_image=self.decode_preview_image,
                on_preview=self.on_preview,
                on_binary_diagnostic=self.on_binary_diagnostic,
                on_visual_diagnostic=self.on_visual_diagnostic,
            ),
        )


__all__ = ["ListenerPreviewEmitter"]
