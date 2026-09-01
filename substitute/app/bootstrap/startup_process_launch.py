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

"""Launch replacement ready-app processes during startup handoff flows."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys
from typing import Any

from substitute.shared.logging.logger import get_logger, log_error, log_exception
from substitute.shared.startup_trace import trace_mark
from sugarsubstitute_shared.application_launch_guard import (
    application_launch_install_root,
    cancel_restart_application_launch_environment,
    restart_application_launch_environment,
)
from sugarsubstitute_shared.launcher_update.targets import (
    detect_launcher_bundle_target,
)
from sugarsubstitute_shared.crash_reporting.protocol import CleanExitOutcome
from sugarsubstitute_shared.crash_reporting.runtime import (
    active_process_crash_runtime,
)
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)

_LOGGER = get_logger("app.bootstrap.startup_process_launch")


def start_ready_app_process(command: Sequence[str]) -> bool:
    """Start a fresh app process for a launch handoff."""

    if not command:
        return False
    startupinfo: Any | None = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW

    working_directory = launch_command_working_directory(command)
    restart_environment = restart_application_launch_environment(command)
    if restart_environment is None:
        log_error(
            _LOGGER,
            "Rejected fresh app process without a controlled restart handoff",
            executable_name=_command_executable_name(command),
            argument_count=len(command),
            working_directory_present=working_directory is not None,
        )
        return False
    supervisor_command, supervisor_working_directory = restart_supervisor_command(
        command
    )
    try:
        subprocess.Popen(  # noqa: S603
            supervisor_command,
            cwd=subprocess_working_directory(supervisor_working_directory),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
            startupinfo=startupinfo,
            env=restart_environment,
        )
    except OSError:
        cancel_restart_application_launch_environment(command, restart_environment)
        log_exception(
            _LOGGER,
            "Failed to start fresh app process",
            executable_name=_command_executable_name(command),
            argument_count=len(command),
            working_directory_present=working_directory is not None,
        )
        return False
    crash_runtime = active_process_crash_runtime()
    if crash_runtime is not None:
        crash_runtime.request_clean_exit(CleanExitOutcome.RESTART)
    trace_mark(
        "ready_app_process.started",
        executable_name=_command_executable_name(command),
        argument_count=len(command),
        working_directory_present=working_directory is not None,
    )
    return True


def restart_supervisor_command(command: Sequence[str]) -> tuple[list[str], Path]:
    """Build the stable launcher command that supervises one app restart."""

    install_root = application_launch_install_root(command, app_root=Path.cwd())
    target = detect_launcher_bundle_target()
    launcher_executable = install_root / target.executable_relative_path
    arguments = (
        "--restart-application",
        f"--install-root={subprocess_path(install_root)}",
    )
    if launcher_executable.is_file():
        return [
            subprocess_path(launcher_executable),
            *arguments,
        ], launcher_executable.parent
    working_directory = launch_command_working_directory(command) or Path.cwd()
    return [
        subprocess_path(Path(sys.executable)),
        "-m",
        "launcher.sugarsubstitute_launcher",
        *arguments,
    ], working_directory


def launch_command_working_directory(command: Sequence[str]) -> Path | None:
    """Return the app entrypoint directory for a runtime launch command."""

    if len(command) < 2:
        return None
    entrypoint = operational_path(command[1])
    if entrypoint.is_file():
        return entrypoint.parent
    return None


def _command_executable_name(command: Sequence[str]) -> str:
    """Return a prompt-safe executable label for launch diagnostics."""

    if not command:
        return ""
    return Path(command[0]).name


__all__ = [
    "launch_command_working_directory",
    "restart_supervisor_command",
    "start_ready_app_process",
]
