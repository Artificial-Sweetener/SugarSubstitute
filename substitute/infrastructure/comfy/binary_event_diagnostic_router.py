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

"""Route top-level Comfy binary event diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
    non_bytes_binary_payload_diagnostic,
    short_binary_frame_diagnostic,
    unencoded_binary_preview_event_diagnostic,
    unknown_binary_event_diagnostic,
)


@dataclass(frozen=True)
class BinaryEventDiagnosticRouter:
    """Map top-level binary event callback data to prompt-safe diagnostics."""

    binary_context: BinaryEventContext
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None]

    def route_non_bytes_payload(self, payload_type: str | None) -> None:
        """Emit the diagnostic for a non-binary websocket payload."""

        self.on_binary_diagnostic(
            non_bytes_binary_payload_diagnostic(
                self.binary_context,
                payload_type=payload_type,
            )
        )

    def route_short_frame(self, payload_length: int | None) -> None:
        """Emit the diagnostic for a short binary websocket frame."""

        self.on_binary_diagnostic(
            short_binary_frame_diagnostic(
                self.binary_context,
                payload_length=payload_length,
            )
        )

    def route_unencoded_preview_event(
        self,
        event_type: int,
        payload_length: int,
    ) -> None:
        """Emit the diagnostic for an unsupported unencoded preview event."""

        self.on_binary_diagnostic(
            unencoded_binary_preview_event_diagnostic(
                self.binary_context,
                event_type=event_type,
                payload_length=payload_length,
            )
        )

    def route_unknown_event(self, event_type: int, payload_length: int) -> None:
        """Emit the diagnostic for an unknown binary websocket event."""

        self.on_binary_diagnostic(
            unknown_binary_event_diagnostic(
                self.binary_context,
                event_type=event_type,
                payload_length=payload_length,
            )
        )


__all__ = ["BinaryEventDiagnosticRouter"]
