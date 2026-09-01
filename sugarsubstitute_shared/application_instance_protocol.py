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

"""Define the bounded protocol shared by the supervisor and application."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol, Self, cast


_MAXIMUM_MESSAGE_BYTES = 1024 * 1024
BROKER_ENDPOINT_ENV = "SUGAR_SUBSTITUTE_INSTANCE_BROKER_ENDPOINT"
BROKER_TOKEN_ENV = "SUGAR_SUBSTITUTE_INSTANCE_BROKER_TOKEN"


class ApplicationInstanceBrokerError(RuntimeError):
    """Report a native election or supervisor communication failure."""


class ApplicationInstanceConnection(Protocol):
    """Expose bounded message frames over one native IPC connection."""

    def send_frame(self, payload: bytes) -> None:
        """Send one complete application-instance frame."""

    def receive_frame(self, maximum_size: int) -> bytes:
        """Receive one frame while rejecting oversized input."""

    def close(self) -> None:
        """Release the native connection idempotently."""


@dataclass(frozen=True, slots=True)
class ApplicationInvocation:
    """Describe one invocation forwarded to the active application."""

    arguments: tuple[str, ...]
    working_directory: str

    @classmethod
    def capture(
        cls,
        arguments: Sequence[str],
        *,
        working_directory: Path | None = None,
    ) -> Self:
        """Capture process launch context without retaining mutable inputs."""

        return cls(
            arguments=tuple(arguments),
            working_directory=str(working_directory or Path.cwd()),
        )

    def to_message(self) -> dict[str, object]:
        """Return the bounded wire representation for this invocation."""

        return {
            "kind": "invoke",
            "arguments": list(self.arguments),
            "working_directory": self.working_directory,
        }


@dataclass(frozen=True, slots=True)
class ApplicationInstanceEndpoint:
    """Identify one OS-owned local endpoint without a filesystem path."""

    transport: str
    address: str
    port: int | None = None

    def to_json(self) -> str:
        """Serialize this endpoint for the supervised child environment."""

        return json.dumps(
            {
                "transport": self.transport,
                "address": self.address,
                "port": self.port,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> Self:
        """Parse a validated endpoint received from the supervisor."""

        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("Application instance endpoint must be an object.")
        transport = payload.get("transport")
        address = payload.get("address")
        port = payload.get("port")
        if transport not in {
            "abstract-unix",
            "loopback-tcp",
            "windows-named-pipe",
        }:
            raise ValueError("Application instance endpoint transport is invalid.")
        if not isinstance(address, str) or not address:
            raise ValueError("Application instance endpoint address is invalid.")
        if port is not None and (not isinstance(port, int) or not 0 < port < 65536):
            raise ValueError("Application instance endpoint port is invalid.")
        return cls(transport=transport, address=address, port=port)


def send_instance_message(
    connection: ApplicationInstanceConnection,
    payload: Mapping[str, object],
) -> None:
    """Send one bounded JSON message through the native transport."""

    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MAXIMUM_MESSAGE_BYTES:
        raise ValueError("Application instance message exceeds its size limit.")
    connection.send_frame(encoded)


def receive_instance_message(
    connection: ApplicationInstanceConnection,
) -> dict[str, object]:
    """Receive and validate one bounded JSON object."""

    payload = json.loads(
        connection.receive_frame(_MAXIMUM_MESSAGE_BYTES).decode("utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError("Application instance message must be an object.")
    return cast(dict[str, object], payload)


def parse_application_invocation(
    message: Mapping[str, object],
) -> ApplicationInvocation:
    """Parse a validated invocation from an untrusted local message."""

    if message.get("kind") != "invoke":
        raise ValueError("Application instance message is not an invocation.")
    raw_arguments = message.get("arguments")
    working_directory = message.get("working_directory")
    if (
        not isinstance(raw_arguments, list)
        or len(raw_arguments) > 256
        or not all(isinstance(argument, str) for argument in raw_arguments)
        or not isinstance(working_directory, str)
    ):
        raise ValueError("Application invocation fields are invalid.")
    return ApplicationInvocation(
        arguments=tuple(cast(list[str], raw_arguments)),
        working_directory=working_directory,
    )


__all__ = [
    "ApplicationInstanceBrokerError",
    "ApplicationInstanceConnection",
    "ApplicationInstanceEndpoint",
    "ApplicationInvocation",
    "BROKER_ENDPOINT_ENV",
    "BROKER_TOKEN_ENV",
    "parse_application_invocation",
    "receive_instance_message",
    "send_instance_message",
]
