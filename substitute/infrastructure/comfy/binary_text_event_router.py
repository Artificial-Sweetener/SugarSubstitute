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

"""Route Comfy binary text events to prompt-safe diagnostics."""

from __future__ import annotations

from typing import Callable

from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    BinaryTextDecodeError,
    decode_binary_text_event,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
    binary_text_event_diagnostic,
    malformed_binary_text_frame_diagnostic,
    short_binary_text_frame_diagnostic,
)


def route_binary_text_event(
    payload: bytes,
    *,
    binary_context: BinaryEventContext,
    on_binary_diagnostic: Callable[[BinaryEventDiagnostic], None],
) -> None:
    """Decode one Comfy binary text event and emit its diagnostic outcome."""

    try:
        text_event = decode_binary_text_event(payload)
    except BinaryTextDecodeError as error:
        if error.reason == "short_frame":
            on_binary_diagnostic(
                short_binary_text_frame_diagnostic(
                    binary_context,
                    payload_length=error.payload_length,
                )
            )
            return
        on_binary_diagnostic(
            malformed_binary_text_frame_diagnostic(
                binary_context,
                node_id_length=error.node_id_length,
                payload_length=error.payload_length,
            )
        )
        return

    on_binary_diagnostic(
        binary_text_event_diagnostic(
            binary_context,
            node_id=text_event.node_id,
            text=text_event.text,
        )
    )


__all__ = ["route_binary_text_event"]
