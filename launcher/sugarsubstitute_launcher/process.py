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

"""Build and start launcher-managed subprocess commands."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_launch_guard import (
    application_launch_install_root,
)
from sugarsubstitute_shared.external_path_failure import external_long_path_error
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
    standard_child_process_dll_search_path,
)
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)


APP_STARTUP_LOG_NAME = "app-startup.log"
APP_STARTUP_TIMEOUT_SECONDS = 5.0
HANDOFF_STARTUP_TIMEOUT_SECONDS = 0.25


class ProcessStartupError(RuntimeError):
    """Raised when a launched child process exits before it is usable."""


def build_continue_install_command(
    *, layout: InstallLayout, handoff_geometry: str | None = None
) -> list[str]:
    """Build the command that resumes setup from the installed launcher."""

    command = [
        subprocess_path(layout.executable_path),
        "--continue-install",
        f"--install-root={subprocess_path(layout.root)}",
    ]
    if handoff_geometry:
        command.append(f"--handoff-geometry={handoff_geometry}")
    return command


def build_app_launch_command(
    *,
    layout: InstallLayout,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build the command that starts the source payload with managed Python."""

    return [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        *extra_args,
    ]


def start_detached(
    command: Sequence[str],
    *,
    startup_timeout_seconds: float = APP_STARTUP_TIMEOUT_SECONDS,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Start a child process hidden and fail if it exits during startup."""

    process, startup_log_path = spawn_detached_process(
        command,
        environment=environment,
    )
    try:
        return_code = process.wait(timeout=startup_timeout_seconds)
    except subprocess.TimeoutExpired:
        return

    startup_detail = _tail_text(startup_log_path)
    compatibility_error = external_long_path_error(
        component="Python",
        path=_command_working_directory(command) or startup_log_path.parent,
        detail=startup_detail,
    )
    if compatibility_error is not None:
        raise compatibility_error
    raise ProcessStartupError(
        "SugarSubstitute exited before the setup window opened. "
        f"Exit code: {return_code}. "
        f"Startup log: {startup_log_path}. "
        f"{startup_detail}"
    )


def spawn_detached_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[subprocess.Popen[bytes], Path]:
    """Start a hidden app child and return its process and diagnostic log path."""

    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW

    startup_log_path = _app_startup_log_path(command)
    startup_log_path.parent.mkdir(parents=True, exist_ok=True)
    with startup_log_path.open("a", encoding="utf-8", errors="replace") as log_file:
        log_file.write("\n--- Starting SugarSubstitute app ---\n")
        log_file.write(" ".join(command) + "\n")
        log_file.flush()
        working_directory = _command_working_directory(command)
        try:
            with standard_child_process_dll_search_path():
                process = subprocess.Popen(  # noqa: S603
                    list(command),
                    cwd=(
                        subprocess_working_directory(working_directory)
                        if working_directory is not None
                        else None
                    ),
                    env=clean_frozen_parent_environment(environment),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    creationflags=creationflags,
                    shell=False,
                    startupinfo=startupinfo,
                )
        except OSError as error:
            compatibility_error = external_long_path_error(
                component="Python",
                path=working_directory or startup_log_path.parent,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise
    return process, startup_log_path


def start_detached_handoff(command: Sequence[str]) -> None:
    """Start a handoff child process without keeping the current window around."""

    start_detached(command, startup_timeout_seconds=HANDOFF_STARTUP_TIMEOUT_SECONDS)


def build_installed_launcher_handoff_command(
    app_command: Sequence[str],
) -> list[str]:
    """Route a prepared app handoff back through its stable supervisor."""

    install_root = application_launch_install_root(app_command, app_root=Path.cwd())
    layout = InstallLayout.from_root(install_root)
    forwarded_arguments = [
        argument
        for argument in app_command
        if argument.startswith(("--handoff-geometry=", "--locale="))
    ]
    return [
        subprocess_path(layout.executable_path),
        f"--install-root={subprocess_path(layout.root)}",
        *forwarded_arguments,
    ]


def start_installed_launcher_handoff(app_command: Sequence[str]) -> None:
    """Start the installed launcher that will supervise the prepared app."""

    start_detached_handoff(build_installed_launcher_handoff_command(app_command))


def _command_working_directory(command: Sequence[str]) -> Path | None:
    """Return the app directory as cwd when the command includes `main.py`."""

    if len(command) < 2:
        return None
    entrypoint = operational_path(command[1])
    if entrypoint.is_file():
        return entrypoint.parent
    return None


def _app_startup_log_path(command: Sequence[str]) -> Path:
    """Resolve the startup log path from an installed app launch command."""

    if len(command) >= 2:
        entrypoint = operational_path(command[1])
        if entrypoint.name.lower() == "main.py":
            return entrypoint.parents[1] / "launcher" / "logs" / APP_STARTUP_LOG_NAME
    return Path.cwd() / APP_STARTUP_LOG_NAME


def _tail_text(path: Path, *, maximum_lines: int = 40) -> str:
    """Return the tail of a text log for startup error reporting."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    tail = lines[-maximum_lines:]
    if not tail:
        return ""
    return "Last startup output:\n" + "\n".join(tail)
