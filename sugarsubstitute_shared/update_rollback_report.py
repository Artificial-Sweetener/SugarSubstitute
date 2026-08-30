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

"""Persist one diagnostic receipt after an application update rolls back."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import traceback as traceback_module
from typing import Mapping, Self

from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)


_REPORT_SCHEMA_VERSION = 1
_REPORT_RELATIVE_PATH = Path("launcher") / "update-rollback-report.json"
_MAX_MESSAGE_CHARACTERS = 4096
_MAX_TRACEBACK_CHARACTERS = 65536


class UpdateRollbackStage(Enum):
    """Identify the update phase restored by a successful rollback."""

    PREPARATION = "preparation"
    CANDIDATE_READINESS = "candidate_readiness"


@dataclass(frozen=True, slots=True)
class UpdateRollbackReport:
    """Describe one failed update whose previous installation was restored."""

    attempted_version: str
    stage: UpdateRollbackStage
    exception_type: str
    message: str
    traceback: str
    occurred_at_utc: str

    @classmethod
    def capture(
        cls,
        *,
        attempted_version: str,
        stage: UpdateRollbackStage,
        error: BaseException,
        now: datetime | None = None,
    ) -> Self:
        """Capture bounded diagnostics without retaining the exception object."""

        occurred_at = now or datetime.now(UTC)
        rendered_traceback = "".join(traceback_module.format_exception(error))
        message = str(error).strip() or repr(error)
        return cls(
            attempted_version=attempted_version,
            stage=stage,
            exception_type=type(error).__name__,
            message=message[:_MAX_MESSAGE_CHARACTERS],
            traceback=rendered_traceback[-_MAX_TRACEBACK_CHARACTERS:],
            occurred_at_utc=(
                occurred_at.astimezone(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        )

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> Self:
        """Parse one exact supported report schema."""

        if payload.get("schema_version") != _REPORT_SCHEMA_VERSION:
            raise ValueError("Unsupported update rollback report schema.")
        attempted_version = _required_text(payload, "attempted_version")
        exception_type = _required_text(payload, "exception_type")
        message = _required_text(payload, "message")
        traceback = _required_text(payload, "traceback")
        occurred_at_utc = _required_text(payload, "occurred_at_utc")
        stage_value = _required_text(payload, "stage")
        try:
            stage = UpdateRollbackStage(stage_value)
        except ValueError as error:
            raise ValueError("Invalid update rollback stage.") from error
        return cls(
            attempted_version=attempted_version,
            stage=stage,
            exception_type=exception_type,
            message=message,
            traceback=traceback,
            occurred_at_utc=occurred_at_utc,
        )

    def to_json(self) -> dict[str, object]:
        """Return the stable persisted receipt representation."""

        return {
            "attempted_version": self.attempted_version,
            "exception_type": self.exception_type,
            "message": self.message,
            "occurred_at_utc": self.occurred_at_utc,
            "schema_version": _REPORT_SCHEMA_VERSION,
            "stage": self.stage.value,
            "traceback": self.traceback,
        }


class UpdateRollbackReportStore:
    """Own the single launcher-to-application rollback report handoff."""

    def __init__(self, install_root: Path) -> None:
        """Resolve the report beneath one exact installation root."""

        self._path = install_root.resolve() / _REPORT_RELATIVE_PATH

    @property
    def path(self) -> Path:
        """Return the exact report path for diagnostics and tests."""

        return self._path

    def save(self, report: UpdateRollbackReport) -> None:
        """Atomically replace the pending report with the latest rollback."""

        write_json_atomic(self._path, report.to_json())

    def load(self) -> UpdateRollbackReport | None:
        """Load the pending report when one exists."""

        try:
            payload = read_json_object(self._path)
        except FileNotFoundError:
            return None
        return UpdateRollbackReport.from_json(payload)

    def acknowledge(self) -> None:
        """Remove a report after its modal has been dismissed."""

        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


def _required_text(payload: Mapping[str, object], key: str) -> str:
    """Return one required non-empty string field."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid update rollback report field: {key}.")
    return value


__all__ = [
    "UpdateRollbackReport",
    "UpdateRollbackReportStore",
    "UpdateRollbackStage",
]
