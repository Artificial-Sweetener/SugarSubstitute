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

"""Persist deterministic terminal evidence for launcher update attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Self

from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)


ATTEMPT_STATUS_RELATIVE_PATH = Path("launcher") / "update-attempt.json"
_ATTEMPT_STATUS_SCHEMA_VERSION = 1


class LauncherUpdateAttemptPhase(str, Enum):
    """Identify an observable launcher-update terminal or active phase."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LauncherUpdateAttemptStatus:
    """Describe the latest launcher update without relying on log parsing."""

    version: str
    phase: LauncherUpdateAttemptPhase
    route: str
    occurred_at_utc: str
    error_type: str | None = None
    error_message: str | None = None

    @classmethod
    def create(
        cls,
        *,
        version: str,
        phase: LauncherUpdateAttemptPhase,
        route: str,
        error: BaseException | None = None,
        now: datetime | None = None,
    ) -> Self:
        """Capture one bounded status record with a stable UTC timestamp."""

        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        return cls(
            version=version,
            phase=phase,
            route=route,
            occurred_at_utc=(
                timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            ),
            error_type=type(error).__name__ if error is not None else None,
            error_message=(str(error).strip() or repr(error))[:2000]
            if error is not None
            else None,
        )

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one exact status schema or reject untrusted persisted data."""

        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported launcher update attempt status schema.")
        version = payload.get("version")
        route = payload.get("route")
        occurred_at = payload.get("occurred_at_utc")
        raw_phase = payload.get("phase")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(route, str)
            or not route
            or not isinstance(occurred_at, str)
            or not occurred_at
            or not isinstance(raw_phase, str)
            or not raw_phase
        ):
            raise ValueError("Launcher update attempt status is invalid.")
        error_type = payload.get("error_type")
        error_message = payload.get("error_message")
        if error_type is not None and not isinstance(error_type, str):
            raise ValueError("Launcher update attempt error type is invalid.")
        if error_message is not None and not isinstance(error_message, str):
            raise ValueError("Launcher update attempt error message is invalid.")
        return cls(
            version=version,
            phase=LauncherUpdateAttemptPhase(raw_phase),
            route=route,
            occurred_at_utc=occurred_at,
            error_type=error_type,
            error_message=error_message,
        )

    def to_json(self) -> dict[str, object]:
        """Return the stable persisted status representation."""

        return {
            "error_message": self.error_message,
            "error_type": self.error_type,
            "occurred_at_utc": self.occurred_at_utc,
            "phase": self.phase.value,
            "route": self.route,
            "schema_version": _ATTEMPT_STATUS_SCHEMA_VERSION,
            "version": self.version,
        }


class LauncherUpdateAttemptStore:
    """Own the latest structured update status for one installation."""

    def __init__(self, install_root: Path) -> None:
        """Resolve status storage beneath the exact installation root."""

        self._path = install_root.resolve() / ATTEMPT_STATUS_RELATIVE_PATH

    @property
    def path(self) -> Path:
        """Return the status path used by launchers and qualification."""

        return self._path

    def save(self, status: LauncherUpdateAttemptStatus) -> None:
        """Atomically publish the latest attempt phase."""

        write_json_atomic(self._path, status.to_json())

    def load(self) -> LauncherUpdateAttemptStatus | None:
        """Load the latest attempt status when one exists."""

        try:
            payload = read_json_object(self._path)
        except FileNotFoundError:
            return None
        return LauncherUpdateAttemptStatus.from_json(payload)


__all__ = [
    "ATTEMPT_STATUS_RELATIVE_PATH",
    "LauncherUpdateAttemptPhase",
    "LauncherUpdateAttemptStatus",
    "LauncherUpdateAttemptStore",
]
