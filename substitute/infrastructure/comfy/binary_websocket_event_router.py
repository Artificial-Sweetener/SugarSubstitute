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

"""Route raw Comfy binary websocket payloads through focused event owners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from substitute.infrastructure.comfy.binary_event_diagnostic_router import (
    BinaryEventDiagnosticRouter,
)
from substitute.infrastructure.comfy.binary_text_event_router import (
    route_binary_text_event,
)
from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    BinaryEventDispatchCallbacks,
    dispatch_binary_websocket_event,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.legacy_preview_router import LegacyPreviewRouter
from substitute.infrastructure.comfy.metadata_preview_router import (
    MetadataPreviewRoutingCallbacks,
    MetadataPreviewRoutingRequest,
    route_metadata_preview_image,
)
from substitute.infrastructure.comfy.preview_emission import PreviewEmissionRequest
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
    VisualEventRequestIdentity,
)


@dataclass(frozen=True)
class BinaryWebsocketRoutingCallbacks:
    """Provide side-effect ports for binary websocket event routing."""

    on_emit_preview: Callable[[PreviewEmissionRequest], None]
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None]
    on_visual_diagnostic: Callable[[VisualEventRejectionDiagnostic], None]


@dataclass(frozen=True)
class BinaryWebsocketRoutingContext:
    """Describe listener context required for binary websocket routing."""

    active_prompt_id: str
    binary_context: BinaryEventContext
    visual_context: VisualEventContext
    request_identity: VisualEventRequestIdentity


class BinaryWebsocketEventRouter:
    """Route Comfy binary websocket payloads to event-specific owners."""

    def __init__(
        self,
        *,
        context: BinaryWebsocketRoutingContext,
        callbacks: BinaryWebsocketRoutingCallbacks,
        legacy_preview_router: LegacyPreviewRouter | None = None,
    ) -> None:
        """Initialize routing context and per-listener legacy preview state."""

        self._context = context
        self._callbacks = callbacks
        self._legacy_preview_router = legacy_preview_router or LegacyPreviewRouter()

    def route_event(self, event_payload: object, *, all_node_ids: set[str]) -> None:
        """Route one raw Comfy binary websocket payload."""

        diagnostic_router = BinaryEventDiagnosticRouter(
            binary_context=self._context.binary_context,
            on_binary_diagnostic=self._callbacks.on_binary_diagnostic,
        )

        dispatch_binary_websocket_event(
            event_payload,
            BinaryEventDispatchCallbacks(
                on_non_bytes_payload=diagnostic_router.route_non_bytes_payload,
                on_short_frame=diagnostic_router.route_short_frame,
                on_preview_image=self._route_legacy_preview_image,
                on_metadata_preview_image=lambda payload, event_type: (
                    self._route_metadata_preview_image(
                        payload,
                        event_type,
                        all_node_ids=all_node_ids,
                    )
                ),
                on_text=self._route_binary_text_event,
                on_unencoded_preview_image=(
                    diagnostic_router.route_unencoded_preview_event
                ),
                on_unknown=diagnostic_router.route_unknown_event,
            ),
        )

    def _route_legacy_preview_image(self, payload: bytes, event_type: int) -> None:
        """Route one metadata-less preview image frame."""

        self._legacy_preview_router.route_preview_image(
            payload,
            binary_event_type=event_type,
            binary_context=self._context.binary_context,
            on_binary_diagnostic=self._callbacks.on_binary_diagnostic,
        )

    def _route_metadata_preview_image(
        self,
        payload: bytes,
        event_type: int,
        *,
        all_node_ids: set[str],
    ) -> None:
        """Route one metadata-bearing preview image frame."""

        route_metadata_preview_image(
            MetadataPreviewRoutingRequest(
                payload=payload,
                binary_event_type=event_type,
                active_prompt_id=self._context.active_prompt_id,
                all_node_ids=all_node_ids,
            ),
            binary_context=self._context.binary_context,
            visual_context=self._context.visual_context,
            request_identity=self._context.request_identity,
            callbacks=MetadataPreviewRoutingCallbacks(
                on_emit_preview=self._callbacks.on_emit_preview,
                on_binary_diagnostic=self._callbacks.on_binary_diagnostic,
                on_visual_diagnostic=self._callbacks.on_visual_diagnostic,
            ),
        )

    def _route_binary_text_event(self, payload: bytes) -> None:
        """Route one binary text payload."""

        route_binary_text_event(
            payload,
            binary_context=self._context.binary_context,
            on_binary_diagnostic=self._callbacks.on_binary_diagnostic,
        )


__all__ = [
    "BinaryWebsocketEventRouter",
    "BinaryWebsocketRoutingCallbacks",
    "BinaryWebsocketRoutingContext",
]
