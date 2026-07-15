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

"""Parse Comfy websocket text events without listener side effects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class TextWebsocketMessage:
    """Describe a decoded Comfy text websocket message."""

    message: dict[str, Any]
    message_type: Any
    data: dict[str, Any]


def parse_text_websocket_message(payload: str) -> TextWebsocketMessage:
    """Decode one text websocket payload and normalize its data mapping."""

    raw_message = json.loads(payload)
    message = cast(dict[str, Any], raw_message)
    message_type = message.get("type")
    data = message.get("data", {})
    if not isinstance(data, dict):
        data = {}
    return TextWebsocketMessage(
        message=message,
        message_type=message_type,
        data=cast(dict[str, Any], data),
    )


__all__ = ["TextWebsocketMessage", "parse_text_websocket_message"]
