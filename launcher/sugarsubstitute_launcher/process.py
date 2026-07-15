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

import contextlib
import ctypes
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


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
        str(layout.executable_path),
        "--continue-install",
        f"--install-root={layout.root}",
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
        str(layout.runtime_python),
        str(layout.app_entrypoint),
        f"--install-root={layout.root}",
        *extra_args,
    ]


def start_detached(
    command: Sequence[str],
    *,
    startup_timeout_seconds: float = APP_STARTUP_TIMEOUT_SECONDS,
) -> None:
    """Start a child process hidden and fail if it exits during startup."""

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
        with _standard_child_process_dll_search_path():
            process = subprocess.Popen(  # noqa: S603
                list(command),
                cwd=_command_working_directory(command),
                env=_child_process_environment(),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=creationflags,
                shell=False,
                startupinfo=startupinfo,
            )
        try:
            return_code = process.wait(timeout=startup_timeout_seconds)
        except subprocess.TimeoutExpired:
            return

    raise ProcessStartupError(
        "SugarSubstitute exited before the setup window opened. "
        f"Exit code: {return_code}. "
        f"Startup log: {startup_log_path}. "
        f"{_tail_text(startup_log_path)}"
    )


def start_detached_handoff(command: Sequence[str]) -> None:
    """Start a handoff child process without keeping the current window around."""

    start_detached(command, startup_timeout_seconds=HANDOFF_STARTUP_TIMEOUT_SECONDS)


def _command_working_directory(command: Sequence[str]) -> Path | None:
    """Return the app directory as cwd when the command includes `main.py`."""

    if len(command) < 2:
        return None
    entrypoint = Path(command[1])
    if entrypoint.is_file():
        return entrypoint.parent
    return None


@contextlib.contextmanager
def _standard_child_process_dll_search_path() -> Iterator[None]:
    """Prevent PyInstaller's DLL search path from leaking into child processes."""

    if sys.platform != "win32" or not bool(getattr(sys, "frozen", False)):
        yield
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    meipass = getattr(sys, "_MEIPASS", None)
    kernel32.SetDllDirectoryW(None)
    try:
        yield
    finally:
        if isinstance(meipass, str) and meipass:
            kernel32.SetDllDirectoryW(meipass)


def _child_process_environment() -> dict[str, str]:
    """Return a subprocess environment independent from PyInstaller internals."""

    environment = os.environ.copy()
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        environment["PATH"] = os.pathsep.join(
            path
            for path in environment.get("PATH", "").split(os.pathsep)
            if path and not _is_relative_to(Path(path), Path(meipass))
        )
    return environment


def _is_relative_to(path: Path, parent: Path) -> bool:
    """Return whether `path` is inside `parent` without requiring Python 3.9 APIs."""

    try:
        path.resolve().relative_to(parent.resolve())
    except OSError:
        return False
    except ValueError:
        return False
    return True


def _app_startup_log_path(command: Sequence[str]) -> Path:
    """Resolve the startup log path from an installed app launch command."""

    if len(command) >= 2:
        entrypoint = Path(command[1])
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
