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

from substitute.shared.logging.logger import get_logger, log_exception
from substitute.shared.startup_trace import trace_mark
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
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
    try:
        subprocess.Popen(  # noqa: S603
            list(command),
            cwd=(
                subprocess_working_directory(working_directory)
                if working_directory is not None
                else None
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
    except OSError:
        log_exception(
            _LOGGER,
            "Failed to start fresh app process",
            executable_name=_command_executable_name(command),
            argument_count=len(command),
            working_directory_present=working_directory is not None,
        )
        return False
    trace_mark(
        "ready_app_process.started",
        executable_name=_command_executable_name(command),
        argument_count=len(command),
        working_directory_present=working_directory is not None,
    )
    return True


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


__all__ = ["launch_command_working_directory", "start_ready_app_process"]
