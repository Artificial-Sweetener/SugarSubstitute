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

"""Provide a controllable onboarding-environment test double."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from substitute.domain.onboarding import (
    ComfyPythonBinding,
)


class _FakeEnvironmentCoordinator(QObject):
    """Expose controllable live environment signals to window contract tests."""

    preflight_changed = Signal(object)
    discovery_finished = Signal(object)
    recovery_changed = Signal(object)
    browse_finished = Signal(object)
    termination_finished = Signal(object)
    task_failed = Signal(str)

    def __init__(self) -> None:
        """Record environment actions requested by the window."""

        super().__init__()
        self.preflight_starts = 0
        self.discoveries: list[Path] = []
        self.recoveries: list[tuple[Path, ComfyPythonBinding | None]] = []
        self.validations: list[tuple[Path, Path]] = []
        self.stops = 0
        self.shutdown_calls = 0

    def start_preflight(self) -> None:
        """Record one live preflight request."""

        self.preflight_starts += 1

    def discover_attached_python(self, workspace: Path) -> None:
        """Record one silent attached-Python discovery request."""

        self.discoveries.append(workspace)

    def start_attached_recovery(
        self,
        *,
        workspace: Path,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Record one live launch-monitor request."""

        self.recoveries.append((workspace, binding))

    def validate_browsed_python(self, *, workspace: Path, executable: Path) -> None:
        """Record one explicit manual Python validation request."""

        self.validations.append((workspace, executable))

    def close_observed_processes(self) -> None:
        """Accept an explicit close request for signal-routing tests."""

    def stop_monitoring(self) -> None:
        """Record one page-owned monitor stop."""

        self.stops += 1

    def shutdown(self) -> None:
        """Record coordinator shutdown with the window."""

        self.shutdown_calls += 1
