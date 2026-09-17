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

"""Bound JSON progress frames for one independently supervised repair execution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast


MAXIMUM_REPAIR_FRAME_BYTES = 64 * 1024
REPAIR_EXECUTION_ENDPOINT_ENV = "SUGAR_SUBSTITUTE_REPAIR_EXECUTION_ENDPOINT"


def encode_repair_frame(message: Mapping[str, object]) -> bytes:
    """Encode a bounded frame without executable object serialization."""
    encoded = json.dumps(message, ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(encoded) > MAXIMUM_REPAIR_FRAME_BYTES:
        raise ValueError("Repair execution frame exceeds its size limit.")
    return encoded + b"\n"


class RepairFrameDecoder:
    """Retain only one bounded incomplete frame across partial socket reads."""

    def __init__(self) -> None:
        """Start with no retained transport bytes."""
        self._pending = bytearray()

    def feed(self, data: bytes) -> list[dict[str, object]]:
        """Return complete object frames and reject oversized or malformed input."""
        messages: list[dict[str, object]] = []
        for index, fragment in enumerate(data.split(b"\n")):
            if index:
                messages.append(self._decode())
                self._pending.clear()
            if len(self._pending) + len(fragment) > MAXIMUM_REPAIR_FRAME_BYTES:
                raise ValueError("Repair execution frame exceeds its size limit.")
            self._pending.extend(fragment)
        return messages

    def finish(self) -> None:
        """Reject a peer that closes before completing its final frame."""
        if self._pending:
            raise ValueError("Repair execution ended with an incomplete frame.")

    def _decode(self) -> dict[str, object]:
        """Parse one inert JSON object with bounded memory and nesting failures."""
        try:
            value = json.loads(self._pending)
        except (ValueError, RecursionError, UnicodeDecodeError) as error:
            raise ValueError("Repair execution frame is malformed.") from error
        if not isinstance(value, dict):
            raise ValueError("Repair execution frame must contain an object.")
        return cast(dict[str, object], value)


def repair_message_details(message: dict[str, object]) -> str:
    """Require textual diagnostics before forwarding to presentation."""
    details = message.get("details")
    if not isinstance(details, str):
        raise ValueError("Repair worker diagnostics are malformed.")
    return details
