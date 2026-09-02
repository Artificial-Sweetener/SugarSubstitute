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

"""Select and run the launcher process that owns Qt presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import LauncherOperatingSystem
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from launcher.sugarsubstitute_launcher.runtime_paths import frozen_support_path
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class LauncherUiProcess(Protocol):
    """Expose the blocking operation required by report recovery."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the launcher UI child and return its exit status."""


class LauncherUiProcessStarter(Protocol):
    """Start one launcher UI child with an explicit environment."""

    def __call__(
        self,
        command: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
    ) -> tuple[LauncherUiProcess, Path]:
        """Start the supplied command and return its process and log path."""


def build_launcher_ui_command(
    layout: InstallLayout,
    arguments: Sequence[str],
) -> tuple[str, ...]:
    """Target the Qt-capable installed child or the current source launcher."""

    executable = subprocess_path(Path(sys.executable))
    if bool(getattr(sys, "frozen", False)):
        installed_ui_executable = _installed_windows_ui_executable(layout)
        if installed_ui_executable is not None:
            executable = subprocess_path(installed_ui_executable)
        return (executable, *arguments)
    return (
        executable,
        "-m",
        "launcher.sugarsubstitute_launcher",
        *arguments,
    )


def start_crash_reporter(
    layout: InstallLayout,
    incident_id: str,
    *,
    process_starter: LauncherUiProcessStarter = spawn_detached_process,
) -> None:
    """Start one nonblocking crash report in the Qt-capable launcher child."""

    process_starter(
        _build_crash_report_command(layout, incident_id, locale_override=None),
        environment=os.environ,
    )


def run_crash_reporter(
    layout: InstallLayout,
    incident_id: str,
    locale_override: str | None,
    *,
    process_starter: LauncherUiProcessStarter = spawn_detached_process,
) -> int:
    """Present one pending crash report before normal launch continues."""

    process, _log_path = process_starter(
        _build_crash_report_command(layout, incident_id, locale_override),
        environment=os.environ,
    )
    return process.wait()


def _build_crash_report_command(
    layout: InstallLayout,
    incident_id: str,
    locale_override: str | None,
) -> tuple[str, ...]:
    """Build one dedicated report invocation without entering setup or repair."""

    arguments = [
        "--launcher-ui-child",
        f"--install-root={subprocess_path(layout.root)}",
        f"--show-crash-report={incident_id}",
    ]
    if locale_override is not None:
        arguments.append(f"--locale={locale_override}")
    return build_launcher_ui_command(layout, arguments)


def _installed_windows_ui_executable(layout: InstallLayout) -> Path | None:
    """Resolve the UI child only from an authoritative installed Windows bundle."""

    if layout.target.operating_system is not LauncherOperatingSystem.WINDOWS:
        return None
    support_path = frozen_support_path()
    if support_path is None:
        return None
    if support_path.resolve() != layout.launcher_support_path.resolve():
        return None
    return layout.launcher_support_path / "LauncherUi.exe"


__all__ = [
    "LauncherUiProcess",
    "LauncherUiProcessStarter",
    "build_launcher_ui_command",
    "run_crash_reporter",
    "start_crash_reporter",
]
