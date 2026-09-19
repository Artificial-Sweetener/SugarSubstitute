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

"""Exchange authenticated instance-recovery decisions with a launcher UI child."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import secrets
from typing import Self
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceFailureReason,
)


_SCHEMA_VERSION = 1
_MAXIMUM_EXCHANGE_BYTES = 16 * 1024


class InstanceRecoveryAction(StrEnum):
    """Describe one user-selected response to failed instance activation."""

    RETRY = "retry"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class InstanceRecoveryRequest:
    """Carry one authenticated UI request and its response destination."""

    token: str
    response_path: Path
    reason: ApplicationInstanceFailureReason

    @classmethod
    def create(
        cls,
        exchange_directory: Path,
        *,
        reason: ApplicationInstanceFailureReason,
    ) -> tuple[Self, Path]:
        """Create one request file in an owner-private temporary directory."""

        exchange_directory.mkdir(parents=True, exist_ok=True)
        request_path = exchange_directory / "request.json"
        request = cls(
            token=secrets.token_urlsafe(32),
            response_path=exchange_directory / "response.json",
            reason=reason,
        )
        return request, request_path

    def write(self, request_path: Path) -> None:
        """Atomically publish the request before starting the UI child."""

        _write_json(
            request_path,
            {
                "schema_version": _SCHEMA_VERSION,
                "token": self.token,
                # Older packaged UI readers require this field; never grant control.
                "can_end_owner": False,
                "response_path": str(self.response_path),
                "reason": self.reason.value,
            },
        )

    @classmethod
    def read(cls, request_path: Path) -> Self:
        """Read and validate one supervisor-authored recovery request."""

        payload = _read_json(request_path)
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("Instance recovery request schema is unsupported.")
        token = payload.get("token")
        raw_response_path = payload.get("response_path")
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(raw_response_path, str)
        ):
            raise ValueError("Instance recovery request is malformed.")
        response_path = Path(raw_response_path)
        if (
            not response_path.is_absolute()
            or response_path.parent.resolve() != request_path.parent.resolve()
        ):
            raise ValueError("Instance recovery response path is invalid.")
        raw_reason = payload.get(
            "reason", ApplicationInstanceFailureReason.UNAVAILABLE.value
        )
        if not isinstance(raw_reason, str):
            raise ValueError("Instance recovery reason is malformed.")
        return cls(
            token,
            response_path,
            ApplicationInstanceFailureReason(raw_reason),
        )

    def write_response(self, action: InstanceRecoveryAction) -> None:
        """Atomically publish one authenticated user decision."""

        _write_json(
            self.response_path,
            {
                "schema_version": _SCHEMA_VERSION,
                "token": self.token,
                "action": action.value,
            },
        )

    def read_response(self) -> InstanceRecoveryAction:
        """Validate and return the exact UI-child decision."""

        payload = _read_json(self.response_path)
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("Instance recovery response schema is unsupported.")
        token = payload.get("token")
        action = payload.get("action")
        if not isinstance(token, str) or not secrets.compare_digest(token, self.token):
            raise ValueError("Instance recovery response token is invalid.")
        if not isinstance(action, str):
            raise ValueError("Instance recovery response action is invalid.")
        return InstanceRecoveryAction(action)


def _read_json(path: Path) -> dict[str, object]:
    """Read one bounded JSON object from the private exchange directory."""

    with path.open("rb") as stream:
        encoded = stream.read(_MAXIMUM_EXCHANGE_BYTES + 1)
    if len(encoded) > _MAXIMUM_EXCHANGE_BYTES:
        raise ValueError("Instance recovery exchange exceeds its size limit.")
    payload = json.loads(encoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Instance recovery exchange must contain a JSON object.")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Replace one exchange document atomically without leaving partial state."""

    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = ["InstanceRecoveryAction", "InstanceRecoveryRequest"]
