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

"""Run launcher-owned QApplications beneath the crash supervisor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys
from typing import Protocol

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import LauncherOperatingSystem
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from launcher.sugarsubstitute_launcher.runtime_paths import frozen_support_path
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class LauncherUiCrashSupervisor(Protocol):
    """Describe the supervision boundary used by launcher UI child modes."""

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Run one launcher UI child until a classified terminal state."""


def supervise_launcher_window(
    *,
    layout: InstallLayout,
    arguments: LauncherArguments,
    repair: bool,
    supervisor: LauncherUiCrashSupervisor | None = None,
) -> int:
    """Run setup or repair UI as a full-lifetime supervised child."""

    child_arguments = [
        "--launcher-ui-child",
        f"--install-root={subprocess_path(layout.root)}",
    ]
    if arguments.continue_install:
        child_arguments.append("--continue-install")
    if repair:
        child_arguments.append("--repair")
    if arguments.no_update_check:
        child_arguments.append("--no-update-check")
    _append_value(child_arguments, "--handoff-geometry", arguments.handoff_geometry)
    _append_value(child_arguments, "--manifest-url", arguments.manifest_url)
    _append_value(child_arguments, "--locale", arguments.locale_override)
    return _supervise(
        layout=layout,
        child_arguments=child_arguments,
        supervisor=supervisor,
    )


def _supervise(
    *,
    layout: InstallLayout,
    child_arguments: Sequence[str],
    supervisor: LauncherUiCrashSupervisor | None,
) -> int:
    """Run one current-launcher child through the shared crash protocol."""

    crash_owner = supervisor or ApplicationCrashSupervisor(
        reporter_starter=_start_current_crash_reporter,
        native_runtime_resolver=_current_native_runtime,
    )
    return crash_owner.supervise(
        layout=layout,
        command=_current_launcher_command(layout, child_arguments),
        environment=os.environ,
    )


def _current_launcher_command(
    layout: InstallLayout,
    arguments: Sequence[str],
) -> tuple[str, ...]:
    """Return the packaged UI child or source module invocation."""

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


def _installed_windows_ui_executable(layout: InstallLayout) -> Path | None:
    """Resolve the UI child only from an authoritative installed Windows bundle."""

    if layout.target.operating_system is not LauncherOperatingSystem.WINDOWS:
        return None
    support_path = frozen_support_path()
    if support_path is None:
        return None
    if support_path.resolve() != layout.launcher_support_path.resolve():
        return None
    return Path(sys.executable).with_name("LauncherUi.exe")


def _current_native_runtime(layout: InstallLayout) -> tuple[Path, Path]:
    """Return Crashpad assets from the current bundle or source checkout."""

    support_path = frozen_support_path()
    if support_path is not None:
        runtime = support_path / "crashpad"
    else:
        repository_root = Path(__file__).resolve().parents[2]
        target_directory = layout.target.key.replace("_", "-")
        runtime = (
            repository_root / "third_party" / "bin" / "crashpad" / target_directory
        )
    return (
        runtime / layout.crashpad_handler_path.name,
        runtime / layout.crashpad_client_library_path.name,
    )


def _start_current_crash_reporter(layout: InstallLayout, incident_id: str) -> None:
    """Start the same stable launcher in non-recursive reporter mode."""

    spawn_detached_process(
        _current_launcher_command(
            layout,
            (
                f"--install-root={subprocess_path(layout.root)}",
                f"--show-crash-report={incident_id}",
            ),
        ),
        environment=os.environ,
    )


def _append_value(arguments: list[str], option: str, value: str | None) -> None:
    """Append one optional internal child argument without shell parsing."""

    if value is not None:
        arguments.append(f"{option}={value}")


__all__ = [
    "LauncherUiCrashSupervisor",
    "supervise_launcher_window",
]
