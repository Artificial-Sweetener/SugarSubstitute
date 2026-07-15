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

"""Emit Comfy preview callbacks from validated visual metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from substitute.application.ports.comfy_gateway import PreviewImageUpdate
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
    undecodable_preview_image_diagnostic,
)
from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.preview_update_factory import (
    build_preview_image_update,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
    visual_preview_missing_identity_diagnostic,
)


@dataclass(frozen=True)
class PreviewEmissionRequest:
    """Describe one preview image frame ready for decode and callback emission."""

    image_bytes: bytes
    prompt_id: str
    binary_event_type: int
    node_id: str | None
    metadata_node_id: str | None = None
    display_node_id: str | None = None
    parent_node_id: str | None = None
    real_node_id: str | None = None
    visual_identity: SubstituteVisualIdentity | None = None
    image_format: int | None = None


@dataclass(frozen=True)
class PreviewEmissionCallbacks:
    """Provide side-effect ports required to emit one preview callback."""

    decode_preview_image: Callable[[bytes], object]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None]
    on_visual_diagnostic: Callable[[VisualEventRejectionDiagnostic], None]


def emit_preview_image(
    request: PreviewEmissionRequest,
    *,
    binary_context: BinaryEventContext,
    visual_context: VisualEventContext,
    callbacks: PreviewEmissionCallbacks,
) -> None:
    """Decode and dispatch one preview image frame or emit a rejection diagnostic."""

    if request.visual_identity is None:
        callbacks.on_visual_diagnostic(
            visual_preview_missing_identity_diagnostic(visual_context)
        )
        return

    try:
        preview_image = callbacks.decode_preview_image(request.image_bytes)
    except Exception as error:
        callbacks.on_binary_diagnostic(
            undecodable_preview_image_diagnostic(
                binary_context,
                node_id=request.node_id,
                image_format=request.image_format,
                event_type=request.binary_event_type,
                payload_length=len(request.image_bytes),
                error=error,
            )
        )
        return

    callbacks.on_preview(
        build_preview_image_update(
            visual_identity=request.visual_identity,
            image=preview_image,
            prompt_id=request.prompt_id,
            node_id=request.node_id,
            metadata_node_id=request.metadata_node_id,
            display_node_id=request.display_node_id,
            parent_node_id=request.parent_node_id,
            real_node_id=request.real_node_id,
        )
    )


__all__ = [
    "PreviewEmissionCallbacks",
    "PreviewEmissionRequest",
    "emit_preview_image",
]
