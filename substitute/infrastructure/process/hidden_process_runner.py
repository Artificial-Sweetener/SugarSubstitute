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

"""Run subprocess commands without opening visible console windows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import subprocess
import sys

from substitute.shared.logging.logger import get_logger, log_info
from sugarsubstitute_shared.windows_long_paths import (
    external_long_path_error,
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)

LogCallback = Callable[[str], None]
CommandResult = subprocess.CompletedProcess[str]

_LOGGER = get_logger(__name__)


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run one hidden subprocess and return captured output."""

    process_cwd = operational_path(cwd)
    command_args = _process_command(command)
    log_info(
        _LOGGER,
        "Executing hidden process command",
        command_label=_command_label(command_args),
        cwd=process_cwd,
    )
    try:
        result = subprocess.run(
            command_args,
            cwd=subprocess_working_directory(process_cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags(),
            env=dict(env) if env is not None else None,
            check=False,
        )
    except OSError as error:
        compatibility_error = external_long_path_error(
            component=_command_label(command_args),
            path=process_cwd,
            detail=error,
        )
        if compatibility_error is not None:
            raise compatibility_error from error
        raise
    if check and result.returncode != 0:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        compatibility_error = external_long_path_error(
            component=_command_label(command_args),
            path=process_cwd,
            detail=detail,
        )
        if compatibility_error is not None:
            raise compatibility_error
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}"
        )
    return result


def stream_command(
    command: Sequence[str],
    *,
    cwd: Path,
    on_line: LogCallback | None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run one hidden subprocess and stream merged stdout/stderr."""

    process_cwd = operational_path(cwd)
    command_args = _process_command(command)
    log_info(
        _LOGGER,
        "Streaming hidden process command",
        command_label=_command_label(command_args),
        cwd=process_cwd,
        timeout_seconds=timeout_seconds,
    )
    proc = subprocess.Popen(
        command_args,
        cwd=subprocess_working_directory(process_cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags(),
        env=dict(env) if env is not None else None,
    )
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                if stripped and on_line is not None:
                    on_line(stripped)
        proc.wait(timeout=timeout_seconds)
        return proc.returncode
    finally:
        if proc.stdout is not None:
            proc.stdout.close()


def stream_command_collecting_output(
    command: Sequence[str],
    *,
    cwd: Path,
    on_line: LogCallback | None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, tuple[str, ...]]:
    """Run one hidden subprocess while retaining merged stdout/stderr records."""

    process_cwd = operational_path(cwd)
    command_args = _process_command(command)
    log_info(
        _LOGGER,
        "Streaming hidden process command and collecting output",
        command_label=_command_label(command_args),
        cwd=process_cwd,
        timeout_seconds=timeout_seconds,
    )
    proc = subprocess.Popen(
        command_args,
        cwd=subprocess_working_directory(process_cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags(),
        env=dict(env) if env is not None else None,
    )
    output_lines: list[str] = []
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                output_lines.append(stripped)
                if stripped and on_line is not None:
                    on_line(stripped)
        proc.wait(timeout=timeout_seconds)
        return proc.returncode, tuple(output_lines)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()


def creation_flags() -> int:
    """Return subprocess flags that avoid visible console windows on Windows."""

    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _command_label(command: Sequence[str]) -> str:
    """Return a bounded diagnostic label for a command argument list."""

    if not command:
        return "<empty>"
    executable = Path(command[0]).name
    if len(command) >= 3 and command[1] == "-m":
        return f"{executable} -m {command[2]}"
    return executable


def _process_command(command: Sequence[str]) -> list[str]:
    """Normalize an absolute executable without rewriting opaque arguments."""

    command_args = list(command)
    if command_args and Path(command_args[0]).is_absolute():
        command_args[0] = subprocess_path(command_args[0])
    return command_args


__all__ = [
    "CommandResult",
    "LogCallback",
    "creation_flags",
    "run_command",
    "stream_command",
    "stream_command_collecting_output",
]
