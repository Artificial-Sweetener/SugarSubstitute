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

"""Own runtime command lifetime independently of output availability."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event
from typing import BinaryIO

from launcher.sugarsubstitute_launcher.process_execution import ChildProcess
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeCommandCancelled
from sugarsubstitute_shared.subprocess_environment import (
    standard_child_process_dll_search_path,
)


class RuntimeCommandExecution:
    """Keep cancellation responsive even when a child never finishes an output line."""

    def __init__(self, cancellation: Event) -> None:
        """Bind this command to its provisioning attempt's cancellation signal."""
        self._cancellation = cancellation

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        output: Callable[[bytes], None],
    ) -> int:
        """Drain bounded output batches and reclaim execution on every exit path."""
        self._check_cancel()
        # Independent file descriptions avoid shared offsets and blocking pipe reads.
        with TemporaryDirectory(prefix="substitute-runtime-") as directory:
            path = Path(directory) / "output"
            with (
                path.open("wb", buffering=0) as writer,
                path.open("rb", buffering=0) as reader,
            ):
                process = _start(command, cwd=cwd, env=env, output_fd=writer.fileno())
                try:
                    pending = b""
                    while True:
                        self._check_cancel()
                        pending = _drain(reader, pending, output)
                        code = process.poll()
                        if code is not None:
                            # The owner has stopped descendants before the final drain.
                            while block := reader.read(65536):
                                pending = _publish(pending + block, output)
                            if pending:
                                output(pending)
                            self._check_cancel()
                            return code
                        self._cancellation.wait(0.05)
                finally:
                    process.kill()
                    process.wait(timeout=10)

    def _check_cancel(self) -> None:
        """Stop admission or active execution without depending on child cooperation."""
        if self._cancellation.is_set():
            raise RuntimeCommandCancelled("Runtime command was cancelled.")


def _drain(reader: BinaryIO, pending: bytes, output: Callable[[bytes], None]) -> bytes:
    """Bound each drain so a continuously writing child cannot starve cancellation."""
    return _publish(pending + reader.read(65536), output)


def _publish(pending: bytes, output: Callable[[bytes], None]) -> bytes:
    """Publish complete lines while retaining a fragmented UTF-8 line intact."""
    lines = pending.split(b"\n")
    for line in lines[:-1]:
        output(line)
    return lines[-1]


def _start(
    command: Sequence[str], *, cwd: Path, env: Mapping[str, str], output_fd: int
) -> ChildProcess:
    """Assign lifetime ownership before runtime command code can execute."""
    with standard_child_process_dll_search_path():
        if sys.platform == "win32":
            from sugarsubstitute_shared.windows_process_family import (
                WindowsProcessFamily,
            )

            return WindowsProcessFamily.start(
                command, environment=env, cwd=cwd, output_fd=output_fd
            )
        from launcher.sugarsubstitute_launcher.runtime_posix_process import (
            PosixRuntimeProcess,
        )

        return PosixRuntimeProcess(command, cwd=cwd, env=env, output_fd=output_fd)
