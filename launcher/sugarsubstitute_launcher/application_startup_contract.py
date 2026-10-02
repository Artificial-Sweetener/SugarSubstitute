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

"""Define process lifetime and cancellation outcomes for application startup."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


DEFAULT_READINESS_TIMEOUT_SECONDS = 3600.0


class CandidateProcess(Protocol):
    """Expose process lifecycle operations used by readiness supervision."""

    @property
    def pid(self) -> int:
        """Return the operating-system process identifier."""

    def poll(self) -> int | None:
        """Return the exit status when the process has ended."""

    def terminate(self) -> None:
        """Request graceful process termination."""

    def kill(self) -> None:
        """Force process termination."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for process termination and return its exit status."""


class ApplicationStartupCancelled(Exception):
    """Carry explicit user cancellation through startup and update supervision."""

    def __init__(self, terminated_process: CandidateProcess | None = None) -> None:
        """Retain a retired process for cancellation-aware run classification."""
        super().__init__("Application startup was cancelled by the user.")
        self.terminated_process = terminated_process


class InstallationStartupDeferred(Exception):
    """Leave a still-owned installation intact instead of requesting repair."""


class ApplicationStartupCompleted(Exception):
    """Carry an authenticated terminal launcher exit without claiming UI readiness."""

    def __init__(self, process: CandidateProcess) -> None:
        """Retain the exited process for its authoritative lifetime classifier."""
        super().__init__("Launcher completed its authenticated startup handoff.")
        self.process = process


class ApplicationReadinessError(RuntimeError):
    """Report a candidate that exits or stalls before its shell is ready."""

    def __init__(
        self,
        message: str,
        *,
        terminated_process: CandidateProcess | None = None,
        incident_id: str | None = None,
        diagnostics: Mapping[str, str] | None = None,
    ) -> None:
        """Retain terminated-process and durable-incident recovery context."""

        super().__init__(message)
        self.terminated_process = terminated_process
        self.incident_id = incident_id
        self.diagnostics = dict(diagnostics or {})

    def add_diagnostics(self, values: Mapping[str, object]) -> None:
        """Add non-secret supervisor facts without replacing specific evidence."""

        for key, value in values.items():
            self.diagnostics.setdefault(key, str(value))
