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
from typing import Literal, Protocol, Self, cast


_MAXIMUM_MESSAGE_BYTES = 1024 * 1024
BROKER_ENDPOINT_ENV = "SUGAR_SUBSTITUTE_INSTANCE_BROKER_ENDPOINT"
BROKER_TOKEN_ENV = "SUGAR_SUBSTITUTE_INSTANCE_BROKER_TOKEN"


class ApplicationInstanceBrokerError(RuntimeError):
    """Report a native election or supervisor communication failure."""

    def __init__(
        self,
        message: str,
        *,
        owner_process_id: int | None = None,
        endpoint: ApplicationInstanceEndpoint | None = None,
    ) -> None:
        """Retain the verified owner and endpoint needed for explicit recovery."""

        super().__init__(message)
        self.owner_process_id = owner_process_id
        self.endpoint = endpoint


class ApplicationInstanceConnection(Protocol):
    """Expose bounded message frames over one native IPC connection."""

    def send_frame(self, payload: bytes) -> None:
        """Send one complete application-instance frame."""

    def receive_frame(
        self,
        maximum_size: int,
        *,
        timeout_seconds: float | None = None,
    ) -> bytes:
        """Receive one bounded frame, optionally within a deadline."""

    def close(self) -> None:
        """Release the native connection idempotently."""

    def peer_process_id(self) -> int | None:
        """Return the kernel-reported peer process when the transport supports it."""


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
class RoutedApplicationInvocation:
    """Bind one forwarded invocation to its presentation acknowledgement."""

    request_id: str
    invocation: ApplicationInvocation

    def to_message(self) -> dict[str, object]:
        """Return the authenticated child-channel wire representation."""

        return {
            **self.invocation.to_message(),
            "request_id": self.request_id,
        }


ApplicationInvocationOutcome = Literal["presented", "unavailable"]


@dataclass(frozen=True, slots=True)
class ApplicationInvocationReceipt:
    """Prove whether a routed invocation produced a usable application surface."""

    request_id: str
    outcome: ApplicationInvocationOutcome
    surface: str

    def to_message(self, *, token: str) -> dict[str, object]:
        """Return the authenticated supervisor-channel wire representation."""

        return {
            "kind": "invocation-receipt",
            "token": token,
            "request_id": self.request_id,
            "outcome": self.outcome,
            "surface": self.surface,
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
    *,
    timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Receive and validate one bounded JSON object within an optional deadline."""

    payload = json.loads(
        connection.receive_frame(
            _MAXIMUM_MESSAGE_BYTES,
            timeout_seconds=timeout_seconds,
        ).decode("utf-8")
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


def parse_routed_application_invocation(
    message: Mapping[str, object],
) -> RoutedApplicationInvocation:
    """Parse a forwarded invocation carrying one bounded request identity."""

    request_id = message.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise ValueError("Application invocation request identity is invalid.")
    return RoutedApplicationInvocation(
        request_id=request_id,
        invocation=parse_application_invocation(message),
    )


def parse_application_invocation_receipt(
    message: Mapping[str, object],
) -> ApplicationInvocationReceipt:
    """Parse a child receipt proving one presentation attempt's outcome."""

    if message.get("kind") != "invocation-receipt":
        raise ValueError("Application instance message is not a receipt.")
    request_id = message.get("request_id")
    outcome = message.get("outcome")
    surface = message.get("surface")
    if (
        not isinstance(request_id, str)
        or not request_id
        or len(request_id) > 128
        or outcome not in {"presented", "unavailable"}
        or not isinstance(surface, str)
        or len(surface) > 256
    ):
        raise ValueError("Application invocation receipt fields are invalid.")
    return ApplicationInvocationReceipt(
        request_id=request_id,
        outcome=outcome,
        surface=surface,
    )


__all__ = [
    "ApplicationInstanceBrokerError",
    "ApplicationInstanceConnection",
    "ApplicationInstanceEndpoint",
    "ApplicationInvocation",
    "ApplicationInvocationOutcome",
    "ApplicationInvocationReceipt",
    "BROKER_ENDPOINT_ENV",
    "BROKER_TOKEN_ENV",
    "RoutedApplicationInvocation",
    "parse_application_invocation_receipt",
    "parse_application_invocation",
    "parse_routed_application_invocation",
    "receive_instance_message",
    "send_instance_message",
]
