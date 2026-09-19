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

"""Own a supervised helper's process lifetime and separate UTF-8 output pipes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
from typing import IO, TYPE_CHECKING, Protocol

from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
    standard_child_process_dll_search_path,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_working_directory

if TYPE_CHECKING:
    from sugarsubstitute_shared.windows_process_family import WindowsProcessFamily


class SupervisedTextProcess:
    """Retain kernel lifetime authority while consumers drain separate output streams."""

    def __init__(
        self,
        process: WindowsProcessFamily | subprocess.Popen[str],
        stdout: IO[str],
        stderr: IO[str],
    ) -> None:
        """Transfer ownership of the lifetime handle and both readable pipes."""
        self._process = process
        self.stdout = stdout
        self.stderr = stderr

    @property
    def pid(self) -> int:
        """Identify the supervised root without exposing native handles."""
        return self._process.pid

    def poll(self) -> int | None:
        """Observe completion through the authoritative process-family owner."""
        return self._process.poll()

    def wait(self, timeout: float | None = None) -> int:
        """Wait for completion and the native adapter's descendant cleanup."""
        return self._process.wait(timeout=timeout)

    def terminate(self) -> None:
        """Request termination through the process-family owner."""
        self._process.terminate()

    def kill(self) -> None:
        """Force termination through the process-family owner."""
        self._process.kill()


class TextProcessStarter(Protocol):
    """Define the process creation boundary used by streamed helper protocols."""

    def __call__(
        self,
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        cwd: Path,
    ) -> SupervisedTextProcess:
        """Return a live helper with independent output and diagnostic streams."""


def start_supervised_text_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
) -> SupervisedTextProcess:
    """Start a helper with atomic Windows containment and explicit pipe ownership."""
    child_environment = clean_frozen_parent_environment(environment)
    with standard_child_process_dll_search_path():
        if sys.platform == "win32":
            return _start_windows(command, environment=child_environment, cwd=cwd)
        process = subprocess.Popen(
            command,
            cwd=subprocess_working_directory(cwd),
            env=child_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    assert process.stdout is not None and process.stderr is not None
    return SupervisedTextProcess(process, process.stdout, process.stderr)


def _start_windows(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
) -> SupervisedTextProcess:
    """Inherit only child-side pipe handles; keep lifetime authority in the parent."""
    from sugarsubstitute_shared.windows_process_family import WindowsProcessFamily

    with ExitStack() as readers, ExitStack() as writers:
        output_read, output_write = os.pipe()
        output = writers.enter_context(os.fdopen(output_write, "wb", buffering=0))
        stdout = readers.enter_context(
            os.fdopen(output_read, "r", encoding="utf-8", errors="replace")
        )
        error_read, error_write = os.pipe()
        error = writers.enter_context(os.fdopen(error_write, "wb", buffering=0))
        stderr = readers.enter_context(
            os.fdopen(error_read, "r", encoding="utf-8", errors="replace")
        )
        family = WindowsProcessFamily.start(
            command,
            environment=environment,
            cwd=Path(subprocess_working_directory(cwd)),
            output_fd=output.fileno(),
            error_fd=error.fileno(),
        )
        process = SupervisedTextProcess(family, stdout, stderr)
        readers.pop_all()
        return process
