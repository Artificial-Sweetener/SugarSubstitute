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

"""Retain platform process-control authority through explicit instance recovery."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import math
from pathlib import Path
import sys
from typing import Protocol

import psutil  # type: ignore[import-untyped]

from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_wait import ProcessWaitApi


class InstanceProcess(Protocol):
    """Expose verified metadata and control bound to one recovery target."""

    def create_time(self) -> float:
        """Return the candidate's process creation identity."""

    def exe(self) -> str:
        """Return the candidate's executable image."""

    def cmdline(self) -> Sequence[str]:
        """Read the candidate invocation for installation scope validation."""

    def cwd(self) -> str:
        """Read the invocation's relative-path resolution context."""

    def terminate(self) -> None:
        """Request the target's platform termination operation."""

    def kill(self) -> None:
        """Force the retained target to exit if graceful termination did not finish."""

    def wait(self, *, timeout: float) -> int | None:
        """Await the retained candidate with a bounded timeout."""


class ProcessControlApi(ProcessWaitApi, Protocol):
    """Add explicit recovery capabilities to read-and-wait process operations."""

    def image_path(self, handle: int) -> Path:
        """Read image identity through the retained process object."""

    def terminate(self, handle: int) -> None:
        """End the object retained by this handle."""


@contextmanager
def open_instance_process(pid: int) -> Iterator[InstanceProcess]:
    """Keep Windows process identity pinned through verification and termination."""
    if sys.platform != "win32":
        yield psutil.Process(pid)
        return
    process = NativeInstanceProcess(pid)
    try:
        yield process
    finally:
        process.close()


class NativeInstanceProcess:
    """Own one Windows handle until explicit recovery reaches a terminal result."""

    def __init__(self, pid: int, *, api: ProcessControlApi | None = None) -> None:
        """Acquire control rights before reading any candidate identity."""
        self._api = api or NativeProcessHandleApi(allow_termination=True)
        self._pid = pid
        handle = self._api.open(pid)
        if handle is None:
            raise psutil.NoSuchProcess(pid)
        self._handle: int | None = handle

    def _retained_handle(self) -> int:
        """Reject use after release instead of acting on a recycled handle value."""
        if self._handle is None:
            raise RuntimeError("Recovery process handle has already been released.")
        return self._handle

    def create_time(self) -> float:
        """Read creation time from the retained process object."""
        return self._api.creation_time(self._retained_handle())

    def exe(self) -> str:
        """Read executable identity without reopening a process by PID."""
        return str(self._api.image_path(self._retained_handle()))

    def cmdline(self) -> Sequence[str]:
        """Read invocation metadata while the retained object pins its PID."""
        self._retained_handle()
        return tuple(psutil.Process(self._pid).cmdline())

    def cwd(self) -> str:
        """Read the invocation context while process identity remains retained."""
        self._retained_handle()
        return str(psutil.Process(self._pid).cwd())

    def terminate(self) -> None:
        """Terminate the exact object whose identity and scope were verified."""
        self._api.terminate(self._retained_handle())

    def kill(self) -> None:
        """Use the same retained Windows termination capability for escalation."""
        self._api.terminate(self._retained_handle())

    def wait(self, timeout: float) -> None:
        """Await the retained process without resolving its PID again."""
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Process wait timeout must be finite and nonnegative.")
        if not self._api.wait(
            self._retained_handle(), min(math.ceil(timeout * 1000), 0xFFFFFFFE)
        ):
            raise psutil.TimeoutExpired(timeout, pid=self._pid)

    def close(self) -> None:
        """Release the control handle exactly once."""
        handle = self._handle
        if handle is not None:
            self._handle = None
            self._api.close(handle)
