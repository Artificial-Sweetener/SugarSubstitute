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

"""Execute runtime subprocess commands with safe streaming diagnostics."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from sugarsubstitute_shared.external_path_failure import external_long_path_error
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
    subprocess_working_directory,
)


_LOGGER = logging.getLogger(__name__)
_FAILURE_OUTPUT_LOG_LINE_LIMIT = 200
_BASIC_AUTH_URL_PATTERN = re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^@\s/]+@")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)=([^\s&]+)"
)
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s]+")


class SubprocessRuntimeCommandRunner:
    """Run runtime commands through subprocess without shell execution."""

    def __init__(self, output_callback: Callable[[str], None] | None = None) -> None:
        """Store the optional output sink used by graphical installers."""

        self._output_callback = output_callback

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run one subprocess command and preserve failure context."""

        executable_name = Path(command[0]).name if command else ""
        _LOGGER.info(
            "Starting runtime command | executable=%s argument_count=%d cwd=%s",
            executable_name,
            len(command),
            cwd,
        )
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW

        process_cwd = operational_path(cwd)
        try:
            process = subprocess.Popen(  # noqa: S603
                list(command),
                cwd=subprocess_working_directory(process_cwd),
                env=dict(env),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except OSError as error:
            compatibility_error = external_long_path_error(
                component=executable_name,
                path=process_cwd,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise
        captured_output: list[str] = []
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = _decode_process_output_line(raw_line)
                if line:
                    captured_output.append(line)
                    if self._output_callback is not None:
                        self._output_callback(line)

        return_code = process.wait()
        if return_code != 0:
            detail = "\n".join(captured_output)
            compatibility_error = external_long_path_error(
                component=executable_name,
                path=process_cwd,
                detail=detail,
            )
            if compatibility_error is not None:
                raise compatibility_error
            for line in captured_output[-_FAILURE_OUTPUT_LOG_LINE_LIMIT:]:
                _LOGGER.error(
                    "Runtime command failure output | executable=%s output=%s",
                    executable_name,
                    _sanitize_runtime_log_line(line),
                )
            _LOGGER.error(
                "Runtime command failed | executable=%s return_code=%d output_line_count=%d",
                executable_name,
                return_code,
                len(captured_output),
            )
            raise subprocess.CalledProcessError(
                return_code,
                list(command),
                output="\n".join(captured_output),
            )
        _LOGGER.info(
            "Runtime command completed | executable=%s return_code=0 output_line_count=%d",
            executable_name,
            len(captured_output),
        )


def _sanitize_runtime_log_line(line: str) -> str:
    """Redact common credential forms before persisting subprocess output."""

    sanitized = _BASIC_AUTH_URL_PATTERN.sub(r"\1<redacted>@", line)
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1=<redacted>", sanitized)
    return _BEARER_TOKEN_PATTERN.sub("Bearer <redacted>", sanitized)


def _decode_process_output_line(raw_line: bytes) -> str:
    """Decode output without depending on platform-specific code pages."""

    return raw_line.decode("utf-8", errors="replace").rstrip()
