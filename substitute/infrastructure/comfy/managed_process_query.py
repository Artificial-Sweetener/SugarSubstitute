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

"""Query operating-system process ownership for managed ComfyUI endpoints."""

from __future__ import annotations

import os
import subprocess

from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("infrastructure.comfy.managed_process_query")
_QUERY_TIMEOUT_SECONDS = 5
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def get_listener_pid(host: str, port: int) -> int | None:
    """Return the listener pid for one local TCP endpoint when available."""

    if host not in _LOCAL_HOSTS:
        return None
    if os.name == "nt":
        return _get_listener_pid_windows(host, port)
    return _get_listener_pid_posix(port)


def get_process_command_line(pid: int) -> str | None:
    """Return the current process command line when the platform can resolve it."""

    if os.name == "nt":
        return _get_process_command_line_windows(pid)
    return _get_process_command_line_posix(pid)


def _get_listener_pid_windows(host: str, port: int) -> int | None:
    """Resolve the Windows owning pid for one listening TCP endpoint."""

    script = (
        "$connection = Get-NetTCPConnection "
        f"-LocalAddress '{host}' -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if ($null -ne $connection) { Write-Output $connection.OwningProcess }"
    )
    result = _run_query(
        ["powershell", "-NoProfile", "-Command", script],
        operation="listener_pid",
        host=host,
        port=port,
    )
    if result is None:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return int(output)
    except ValueError:
        log_debug(
            _LOGGER,
            "Unexpected Windows listener pid output",
            host=host,
            port=port,
            output=output,
        )
        return None


def _get_process_command_line_windows(pid: int) -> str | None:
    """Return the Windows command line for one pid when it can be queried."""

    script = (
        "$process = Get-CimInstance Win32_Process "
        f'-Filter "ProcessId = {pid}" '
        "-ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if ($null -ne $process) { Write-Output $process.CommandLine }"
    )
    result = _run_query(
        ["powershell", "-NoProfile", "-Command", script],
        operation="process_command_line",
        pid=pid,
    )
    if result is None:
        return None
    output = result.stdout.strip()
    return output or None


def _get_listener_pid_posix(port: int) -> int | None:
    """Resolve the POSIX owning pid for one listening TCP endpoint."""

    commands = (
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        ["ss", "-ltnp", f"sport = :{port}"],
    )
    for command in commands:
        result = _run_query(command, operation="listener_pid", port=port)
        if result is None:
            continue
        pid = _parse_posix_listener_pid(command[0], result.stdout)
        if pid is not None:
            return pid
    return None


def _get_process_command_line_posix(pid: int) -> str | None:
    """Return the POSIX command line for one pid when it can be queried."""

    result = _run_query(
        ["ps", "-p", str(pid), "-o", "command="],
        operation="process_command_line",
        pid=pid,
    )
    if result is None:
        return None
    output = result.stdout.strip()
    return output or None


def _run_query(
    command: list[str],
    *,
    operation: str,
    host: str | None = None,
    port: int | None = None,
    pid: int | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Run one bounded process query and degrade unavailable diagnostics safely."""

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log_warning(
            _LOGGER,
            "Managed process query was unavailable",
            operation=operation,
            host=host,
            port=port,
            pid=pid,
            error_type=type(error).__name__,
        )
        return None


def _parse_posix_listener_pid(command_name: str, output: str) -> int | None:
    """Extract one pid from common POSIX listener query outputs."""

    stripped = output.strip()
    if not stripped:
        return None
    if command_name == "lsof":
        first_line = stripped.splitlines()[0].strip()
        return int(first_line) if first_line.isdigit() else None
    marker = "pid="
    start = stripped.find(marker)
    if start == -1:
        return None
    start += len(marker)
    digits: list[str] = []
    for character in stripped[start:]:
        if not character.isdigit():
            break
        digits.append(character)
    return int("".join(digits)) if digits else None


__all__ = ["get_listener_pid", "get_process_command_line"]
