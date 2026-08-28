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
from enum import Enum
from typing import Final


READINESS_PATH_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_PATH"
READINESS_TOKEN_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_TOKEN"
READINESS_SCHEMA_VERSION: Final = 3
_LEGACY_READINESS_SCHEMA_VERSION: Final = 1
_SURFACE_READINESS_SCHEMA_VERSION: Final = 2


class ApplicationReadinessSurface(str, Enum):
    """Identify which visible application surface became ready."""

    LEGACY_VISIBLE_SHELL = "legacy_visible_shell"
    ONBOARDING = "onboarding"
    MAIN_SHELL = "main_shell"


@dataclass(frozen=True, slots=True)
class ApplicationReadinessReceipt:
    """Identify the process and private launch token that became ready."""

    pid: int
    token: str
    surface: ApplicationReadinessSurface
    parent_pid: int | None

    def to_json(self) -> dict[str, object]:
        """Return the stable receipt representation."""

        return {
            "parent_pid": self.parent_pid,
            "pid": self.pid,
            "schema_version": READINESS_SCHEMA_VERSION,
            "surface": self.surface.value,
            "token": self.token,
        }

    @classmethod
    def from_json(cls, payload: object) -> ApplicationReadinessReceipt:
        """Parse one validated receipt or reject malformed external data."""

        if not isinstance(payload, dict):
            raise ValueError("Application readiness receipt must be an object.")
        pid = payload.get("pid")
        token = payload.get("token")
        schema_version = payload.get("schema_version")
        raw_surface = payload.get("surface")
        if (
            schema_version
            not in {
                _LEGACY_READINESS_SCHEMA_VERSION,
                _SURFACE_READINESS_SCHEMA_VERSION,
                READINESS_SCHEMA_VERSION,
            }
            or not isinstance(pid, int)
            or pid <= 0
            or not isinstance(token, str)
            or not token
        ):
            raise ValueError("Application readiness receipt is invalid.")
        if schema_version == _LEGACY_READINESS_SCHEMA_VERSION and raw_surface is None:
            return cls(
                pid=pid,
                token=token,
                surface=ApplicationReadinessSurface.LEGACY_VISIBLE_SHELL,
                parent_pid=None,
            )
        if not isinstance(raw_surface, str):
            raise ValueError("Application readiness receipt is invalid.")
        parent_pid = payload.get("parent_pid")
        if schema_version == READINESS_SCHEMA_VERSION and (
            not isinstance(parent_pid, int) or parent_pid <= 0
        ):
            raise ValueError("Application readiness receipt is invalid.")
        if schema_version != READINESS_SCHEMA_VERSION:
            parent_pid = None
        try:
            surface = ApplicationReadinessSurface(raw_surface)
        except ValueError as error:
            raise ValueError("Application readiness receipt is invalid.") from error
        return cls(
            pid=pid,
            token=token,
            surface=surface,
            parent_pid=parent_pid,
        )


__all__ = [
    "ApplicationReadinessReceipt",
    "ApplicationReadinessSurface",
    "READINESS_PATH_ENV",
    "READINESS_SCHEMA_VERSION",
    "READINESS_TOKEN_ENV",
]
