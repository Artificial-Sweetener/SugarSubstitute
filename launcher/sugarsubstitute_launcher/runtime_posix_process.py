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

"""Own the POSIX process group for one launcher runtime command."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import signal
import subprocess
import sys

import psutil  # type: ignore[import-untyped]

from sugarsubstitute_shared.windows_long_paths import subprocess_working_directory


class PosixRuntimeProcess:
    """Keep package-manager descendants in a dedicated POSIX process group."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        output_fd: int,
    ) -> None:
        """Create the process group atomically with child execution."""
        self._process = subprocess.Popen(  # noqa: S603
            list(command),
            cwd=subprocess_working_directory(cwd),
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=output_fd,
            stderr=output_fd,
            start_new_session=True,
            shell=False,
        )
        self.pid = self._process.pid
        self._identity = psutil.Process(self.pid)
        self._stopped = False

    def poll(self) -> int | None:
        """Keep the root waitable until group termination prevents PID reuse."""
        if self._process.returncode is not None:
            return self._process.returncode
        if self._identity.status() != psutil.STATUS_ZOMBIE:
            return None
        self.kill()
        return self._process.wait()

    def wait(self, timeout: float | None = None) -> int:
        """Reap the root after group termination."""
        return self._process.wait(timeout=timeout)

    def kill(self) -> None:
        """Terminate only this command's retained process-group identity."""
        if sys.platform == "win32":
            raise RuntimeError("POSIX runtime ownership is unavailable on Windows.")
        if self._stopped:
            return
        try:
            os.killpg(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # An exited group has already satisfied cleanup.
        self._stopped = True

    def terminate(self) -> None:
        """Use the same unconditional cleanup for blocked package-manager children."""
        self.kill()
