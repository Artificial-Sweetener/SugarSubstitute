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

    command_args = list(command)
    log_info(
        _LOGGER,
        "Executing hidden process command",
        command_label=_command_label(command_args),
        cwd=cwd,
    )
    result = subprocess.run(
        command_args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags(),
        env=dict(env) if env is not None else None,
        check=False,
    )
    if check and result.returncode != 0:
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

    command_args = list(command)
    log_info(
        _LOGGER,
        "Streaming hidden process command",
        command_label=_command_label(command_args),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
    proc = subprocess.Popen(
        command_args,
        cwd=str(cwd),
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

    command_args = list(command)
    log_info(
        _LOGGER,
        "Streaming hidden process command and collecting output",
        command_label=_command_label(command_args),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
    proc = subprocess.Popen(
        command_args,
        cwd=str(cwd),
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


__all__ = [
    "CommandResult",
    "LogCallback",
    "creation_flags",
    "run_command",
    "stream_command",
    "stream_command_collecting_output",
]
