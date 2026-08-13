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

"""Define the process-bound readiness receipt shared by launcher and app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


READINESS_PATH_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_PATH"
READINESS_TOKEN_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_TOKEN"
READINESS_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class ApplicationReadinessReceipt:
    """Identify the process and private launch token that became ready."""

    pid: int
    token: str

    def to_json(self) -> dict[str, object]:
        """Return the stable receipt representation."""

        return {
            "pid": self.pid,
            "schema_version": READINESS_SCHEMA_VERSION,
            "token": self.token,
        }

    @classmethod
    def from_json(cls, payload: object) -> ApplicationReadinessReceipt:
        """Parse one validated receipt or reject malformed external data."""

        if not isinstance(payload, dict):
            raise ValueError("Application readiness receipt must be an object.")
        pid = payload.get("pid")
        token = payload.get("token")
        if (
            payload.get("schema_version") != READINESS_SCHEMA_VERSION
            or not isinstance(pid, int)
            or pid <= 0
            or not isinstance(token, str)
            or not token
        ):
            raise ValueError("Application readiness receipt is invalid.")
        return cls(pid=pid, token=token)


__all__ = [
    "ApplicationReadinessReceipt",
    "READINESS_PATH_ENV",
    "READINESS_SCHEMA_VERSION",
    "READINESS_TOKEN_ENV",
]
