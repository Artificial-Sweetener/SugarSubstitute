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

"""Route metadata-bearing Comfy preview frames to diagnostics or emission."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    BinaryPreviewMetadata,
    BinaryPreviewMetadataDecodeError,
    MetadataPreviewPayloadDecodeError,
    decode_metadata_preview_payload,
    decode_preview_metadata,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
    malformed_metadata_preview_frame_diagnostic,
    malformed_preview_metadata_diagnostic,
    metadata_preview_missing_prompt_id_diagnostic,
    metadata_preview_missing_source_node_diagnostic,
    metadata_preview_prompt_mismatch_diagnostic,
    short_metadata_preview_frame_diagnostic,
)
from substitute.infrastructure.comfy.preview_emission import PreviewEmissionRequest
from substitute.infrastructure.comfy.preview_source_resolver import (
    resolve_preview_metadata_node_id,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
    VisualEventRequestIdentity,
    substitute_visual_identity_rejection_reason,
    visual_event_rejection_diagnostic,
)


@dataclass(frozen=True)
class MetadataPreviewRoutingRequest:
    """Describe one metadata-bearing preview frame in listener context."""

    payload: bytes
    binary_event_type: int
    active_prompt_id: str
    all_node_ids: set[str]


@dataclass(frozen=True)
class MetadataPreviewRoutingCallbacks:
    """Provide side-effect ports for metadata-preview routing outcomes."""

    on_emit_preview: Callable[[PreviewEmissionRequest], None]
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None]
    on_visual_diagnostic: Callable[[VisualEventRejectionDiagnostic], None]


def route_metadata_preview_image(
    request: MetadataPreviewRoutingRequest,
    *,
    binary_context: BinaryEventContext,
    visual_context: VisualEventContext,
    request_identity: VisualEventRequestIdentity,
    callbacks: MetadataPreviewRoutingCallbacks,
) -> None:
    """Validate one metadata preview frame and route it to emission or diagnostics."""

    try:
        preview_payload = decode_metadata_preview_payload(request.payload)
    except MetadataPreviewPayloadDecodeError as error:
        if error.reason == "short_frame":
            callbacks.on_binary_diagnostic(
                short_metadata_preview_frame_diagnostic(
                    binary_context,
                    payload_length=error.payload_length,
                )
            )
            return
        callbacks.on_binary_diagnostic(
            malformed_metadata_preview_frame_diagnostic(
                binary_context,
                metadata_length=error.metadata_length,
                payload_length=error.payload_length,
            )
        )
        return

    try:
        metadata = decode_preview_metadata(preview_payload.metadata_payload)
    except BinaryPreviewMetadataDecodeError as error:
        callbacks.on_binary_diagnostic(
            malformed_preview_metadata_diagnostic(
                binary_context,
                payload_length=len(preview_payload.metadata_payload),
                error=error,
            )
        )
        metadata = BinaryPreviewMetadata()

    if metadata.prompt_id is None:
        callbacks.on_binary_diagnostic(
            metadata_preview_missing_prompt_id_diagnostic(binary_context)
        )
        return
    if metadata.prompt_id != request.active_prompt_id:
        callbacks.on_binary_diagnostic(
            metadata_preview_prompt_mismatch_diagnostic(
                binary_context,
                event_prompt_id=metadata.prompt_id,
            )
        )
        return

    event_visual_context = replace(
        visual_context,
        node_id=metadata.node_id,
        display_node_id=metadata.display_node_id,
    )
    rejection_reason = substitute_visual_identity_rejection_reason(
        metadata.substitute,
        request_identity,
        prompt_id=metadata.prompt_id,
    )
    if rejection_reason is not None:
        callbacks.on_visual_diagnostic(
            visual_event_rejection_diagnostic(
                rejection_reason,
                metadata.substitute,
                event_visual_context,
                event_prompt_id=metadata.prompt_id,
            )
        )
        return

    node_id = resolve_preview_metadata_node_id(
        metadata,
        all_node_ids=request.all_node_ids,
    )
    if node_id is None:
        callbacks.on_binary_diagnostic(
            metadata_preview_missing_source_node_diagnostic(
                binary_context,
                metadata_node_id=metadata.node_id,
                metadata_display_node_id=metadata.display_node_id,
            )
        )
        return

    callbacks.on_emit_preview(
        PreviewEmissionRequest(
            image_bytes=preview_payload.image_payload,
            prompt_id=request.active_prompt_id,
            binary_event_type=request.binary_event_type,
            node_id=node_id,
            metadata_node_id=metadata.node_id,
            display_node_id=metadata.display_node_id,
            parent_node_id=metadata.parent_node_id,
            real_node_id=metadata.real_node_id,
            visual_identity=metadata.substitute,
            image_format=None,
        )
    )


__all__ = [
    "MetadataPreviewRoutingCallbacks",
    "MetadataPreviewRoutingRequest",
    "route_metadata_preview_image",
]
