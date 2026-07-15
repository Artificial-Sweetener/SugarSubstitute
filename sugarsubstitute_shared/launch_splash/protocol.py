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

"""Encode and validate local launch-splash session messages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Final


MAX_SPLASH_MESSAGE_BYTES: Final = 16 * 1024
SUPPORTED_SPLASH_MESSAGE_TYPES: Final = frozenset({"log", "status", "fatal", "close"})


class SplashSessionMessageError(ValueError):
    """Raised when a splash session message is malformed or unauthorized."""


@dataclass(frozen=True, slots=True)
class SplashSessionMessage:
    """Represent one authenticated splash session message."""

    message_type: str
    token: str
    line: str | None = None


def encode_splash_session_message(message: SplashSessionMessage) -> bytes:
    """Serialize one splash session message as newline-delimited JSON bytes."""

    _validate_message(message)
    payload: dict[str, str] = {
        "type": message.message_type,
        "token": message.token,
    }
    if message.line is not None:
        payload["line"] = message.line
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) > MAX_SPLASH_MESSAGE_BYTES:
        raise SplashSessionMessageError("Splash session message is too large.")
    return encoded + b"\n"


def decode_splash_session_message(
    raw_message: bytes,
    *,
    expected_token: str,
) -> SplashSessionMessage:
    """Decode and authenticate one newline-delimited splash session message."""

    if len(raw_message) > MAX_SPLASH_MESSAGE_BYTES:
        raise SplashSessionMessageError("Splash session message is too large.")
    try:
        payload = json.loads(raw_message.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SplashSessionMessageError(
            "Splash session message is invalid JSON."
        ) from error
    if not isinstance(payload, dict):
        raise SplashSessionMessageError("Splash session message must be an object.")
    message_type = payload.get("type")
    token = payload.get("token")
    line = payload.get("line")
    if not isinstance(message_type, str):
        raise SplashSessionMessageError("Splash session message type is missing.")
    if not isinstance(token, str):
        raise SplashSessionMessageError("Splash session token is missing.")
    if token != expected_token:
        raise SplashSessionMessageError("Splash session token is invalid.")
    if line is not None and not isinstance(line, str):
        raise SplashSessionMessageError("Splash session line must be text.")
    message = SplashSessionMessage(
        message_type=message_type,
        token=token,
        line=line,
    )
    _validate_message(message)
    return message


def _validate_message(message: SplashSessionMessage) -> None:
    """Reject unsupported message shapes before transport writes or dispatch."""

    if message.message_type not in SUPPORTED_SPLASH_MESSAGE_TYPES:
        raise SplashSessionMessageError(
            f"Unsupported splash session message type: {message.message_type}"
        )
    if not message.token:
        raise SplashSessionMessageError("Splash session token must not be empty.")
    if message.message_type != "close" and not message.line:
        raise SplashSessionMessageError(
            "Splash session log, status, and fatal messages require text."
        )
    if message.message_type == "close" and message.line is not None:
        raise SplashSessionMessageError(
            "Splash session close messages cannot include text."
        )
