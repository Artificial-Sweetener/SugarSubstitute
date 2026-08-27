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

"""Provide shell and splash lifecycle test doubles."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


class _Splash:
    """Record splash log lines."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self._calls.append(f"splash_log:{line}")

    def close(self) -> None:
        """Record one splash close request."""

        self._calls.append("splash_close")


class _CloseSplash:
    """Record close requests for reveal tests."""

    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        """Store the call recorder and failure mode."""

        self._calls = calls
        self._fail = fail

    def close(self) -> None:
        """Record and optionally fail a splash close."""

        self._calls.append("splash:close")
        if self._fail:
            raise RuntimeError("splash close failed")
