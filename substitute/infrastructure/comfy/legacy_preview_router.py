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

"""Route legacy metadata-less Comfy preview frames."""

from __future__ import annotations

from typing import Callable

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
    metadata_less_preview_frame_diagnostic,
)


class LegacyPreviewRouter:
    """Drop metadata-less preview frames and warn once per listener run."""

    def __init__(self) -> None:
        """Initialize the one-shot warning state."""

        self._warning_emitted = False

    def route_preview_image(
        self,
        payload: bytes,
        *,
        binary_event_type: int,
        binary_context: BinaryEventContext,
        on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None],
    ) -> None:
        """Drop one legacy preview frame and emit the first warning diagnostic."""

        if self._warning_emitted:
            return
        self._warning_emitted = True
        on_binary_diagnostic(
            metadata_less_preview_frame_diagnostic(
                binary_context,
                event_type=binary_event_type,
                payload_length=len(payload),
            )
        )


__all__ = ["LegacyPreviewRouter"]
