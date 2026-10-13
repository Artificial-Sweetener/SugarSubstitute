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

"""Record kernel-backed launcher ancestry before short-lived runtimes exit."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Final

import psutil  # type: ignore[import-untyped]

from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
)


LAUNCHER_PROCESS_EVENT: Final = "Launcher process identity | "


@dataclass(frozen=True, slots=True)
class LauncherProcessEvidence:
    """Preserve runtime and parent incarnations for diagnostic launch correlation."""

    identity: ProcessIdentity
    parent_identity: ProcessIdentity
    executable: str
    parent_executable: str

    def __post_init__(self) -> None:
        """Reject incomplete ancestry rather than allowing PID-only qualification."""
        for identity in (self.identity, self.parent_identity):
            if isinstance(identity.pid, bool) or identity.pid <= 0:
                raise ValueError("Launcher process identity requires a positive PID.")
        if (
            self.identity.pid == self.parent_identity.pid
            or self.parent_identity.created_at > self.identity.created_at
        ):
            raise ValueError("Launcher process parent identity is inconsistent.")
        for executable in (self.executable, self.parent_executable):
            if not executable.strip() or "\x00" in executable:
                raise ValueError("Launcher process evidence requires executable paths.")

    def to_json(self) -> dict[str, object]:
        """Keep both creation timestamps intact in one atomic diagnostic record."""
        return {
            "identity": {
                "pid": self.identity.pid,
                "created_at": self.identity.created_at,
            },
            "parent_identity": {
                "pid": self.parent_identity.pid,
                "created_at": self.parent_identity.created_at,
            },
            "executable": self.executable,
            "parent_executable": self.parent_executable,
        }

    @classmethod
    def from_json(cls, payload: object) -> LauncherProcessEvidence:
        """Reject missing or malformed diagnostic evidence without inventing fields."""
        if not isinstance(payload, dict):
            raise ValueError("Launcher process evidence must be an object.")
        return cls(
            identity=_parse_identity(payload.get("identity")),
            parent_identity=_parse_identity(payload.get("parent_identity")),
            executable=_required_executable(payload, "executable"),
            parent_executable=_required_executable(payload, "parent_executable"),
        )


def capture_launcher_process_evidence() -> LauncherProcessEvidence:
    """Capture current ancestry while refusing reparented or reused parent PIDs."""
    try:
        process = psutil.Process()
        identity = ProcessIdentity(process.pid, float(process.create_time()))
        parent_pid = int(process.ppid())
        if parent_pid <= 0:
            raise ProcessIdentityError("Launcher process has no inspectable parent.")
        parent = psutil.Process(parent_pid)
        evidence = LauncherProcessEvidence(
            identity=identity,
            parent_identity=ProcessIdentity(parent.pid, float(parent.create_time())),
            executable=str(process.exe()),
            parent_executable=str(parent.exe()),
        )
        if int(process.ppid()) != parent_pid or not parent.is_running():
            raise ProcessIdentityError(
                "Launcher process parent changed during capture."
            )
        return evidence
    except (psutil.Error, OSError, ValueError) as error:
        raise ProcessIdentityError(
            "Could not capture launcher process identity and parent executable."
        ) from error


def _parse_identity(payload: object) -> ProcessIdentity:
    """Require kernel creation time and a real positive PID for each incarnation."""
    if not isinstance(payload, dict):
        raise ValueError("Launcher process identity must be an object.")
    pid = payload.get("pid")
    created_at = payload.get("created_at")
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or not isinstance(created_at, (int, float))
        or isinstance(created_at, bool)
    ):
        raise ValueError("Launcher process identity fields are invalid.")
    try:
        return ProcessIdentity(pid, float(created_at))
    except OverflowError as error:
        raise ValueError("Launcher process creation time is invalid.") from error


def _required_executable(payload: Mapping[object, object], field: str) -> str:
    """Preserve executable spelling while rejecting absent or non-text values."""
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"Launcher process evidence requires {field}.")
    return value


__all__ = [
    "LAUNCHER_PROCESS_EVENT",
    "LauncherProcessEvidence",
    "capture_launcher_process_evidence",
]
