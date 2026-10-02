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

"""Provide the external process and pipe boundary for splash lifecycle proofs."""

from io import StringIO
from typing import IO


class SplashProcessDouble:
    """Provide the process-control and text-pipe boundary used by splash startup."""

    def __init__(
        self,
        *,
        stdout: str,
        wait_times_out_while_running: bool = False,
    ) -> None:
        """Create fake text pipes."""

        self.pid = 1234
        self.stdout: IO[str] = StringIO(stdout)
        self.stderr = StringIO("")
        self.terminated = False
        self.killed = False
        self.wait_timeouts: list[float] = []
        self.wait_times_out_while_running = wait_times_out_while_running

    def poll(self) -> int | None:
        """Report the fake process as running until it is terminated."""

        return 0 if self.terminated or self.killed else None

    def terminate(self) -> None:
        """Record graceful process termination."""

        self.terminated = True

    def kill(self) -> None:
        """Record forced process termination."""

        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        """Record the bounded wait and report successful process exit."""

        if timeout is not None:
            self.wait_timeouts.append(timeout)
        if (
            self.wait_times_out_while_running
            and not self.terminated
            and not self.killed
        ):
            import subprocess

            raise subprocess.TimeoutExpired("splash", timeout or 0.0)
        return 0
