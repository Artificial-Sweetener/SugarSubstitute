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

"""Contain supervised descendants from their first instruction through owner death."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
from ctypes import wintypes
import logging
import math
from pathlib import Path
import subprocess
from threading import Event, RLock
import time
import uuid
import weakref

from sugarsubstitute_shared.windows_process_job_api import (
    APPLICATION_PROCESS_FAMILY_ENV,
    ExtendedLimits,
    BasicAccounting,
    load_kernel,
)
from sugarsubstitute_shared.windows_process_creation import create_windows_process
from sugarsubstitute_shared.windows_job_completion import WindowsJobCompletion

_LOGGER = logging.getLogger(__name__)
_KILL_ON_JOB_CLOSE = 0x2000
_ALLOW_EXPLICIT_BREAKAWAY = 0x0800
_CREATE_NO_WINDOW = 0x08000000
_WAIT_TIMEOUT = 258


class WindowsProcessFamily:
    """Own a kernel-enforced process family without depending on child cooperation."""

    def __init__(
        self, *, job: int, process: int, pid: int, args: Sequence[str]
    ) -> None:
        """Retain non-inheritable lifetime handles in the supervising process only."""
        self._kernel = load_kernel()
        self._job = job
        self._process = process
        self._completion = WindowsJobCompletion(job)
        self.pid = pid
        self.args = tuple(args)
        self.returncode: int | None = None
        self._lock = RLock()
        self._release = weakref.finalize(
            self, _release_handles, self._kernel, job, process
        )

    @classmethod
    def start(
        cls,
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        cwd: Path | None,
        output_fd: int,
        error_fd: int | None = None,
        allow_breakaway: bool = False,
    ) -> WindowsProcessFamily:
        """Assign the child atomically, eliminating the spawn-before-containment gap."""
        kernel = load_kernel()
        job_name = f"Local\\SugarSubstitute-family-{uuid.uuid4()}"
        job = kernel.CreateJobObjectW(None, job_name)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = _KILL_ON_JOB_CLOSE
        if allow_breakaway:
            limits.basic.flags |= _ALLOW_EXPLICIT_BREAKAWAY
        try:
            if not kernel.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            child_environment = dict(environment)
            child_environment[APPLICATION_PROCESS_FAMILY_ENV] = job_name
            process_info = create_windows_process(
                command,
                environment=child_environment,
                cwd=cwd,
                output_fd=output_fd,
                error_fd=error_fd,
                job=job,
                creation_flags=_CREATE_NO_WINDOW,
            )
            kernel.CloseHandle(process_info.thread)
            family = cls(
                job=job,
                process=process_info.process,
                pid=process_info.pid,
                args=command,
            )
            _LOGGER.info(
                "Started kernel-owned process family | child_pid=%s", family.pid
            )
            job = None
            return family
        finally:
            if job:
                kernel.CloseHandle(job)

    def poll(self) -> int | None:
        """Observe exit and release descendants when the supervised root has ended."""
        with self._lock:
            if self.returncode is not None:
                return self.returncode
            result = self._kernel.WaitForSingleObject(self._process, 0)
            if result == _WAIT_TIMEOUT:
                return None
            if result != 0:
                raise ctypes.WinError(ctypes.get_last_error())
            return self._finish()

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the supervised root and reclaim its entire remaining family."""
        with self._lock:
            if self.returncode is not None:
                return self.returncode
            duplicate = wintypes.HANDLE()
            current_process = self._kernel.GetCurrentProcess()
            if not self._kernel.DuplicateHandle(
                current_process,
                self._process,
                current_process,
                ctypes.byref(duplicate),
                0,
                False,
                2,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            handle = duplicate.value
        milliseconds = (
            0xFFFFFFFF
            if timeout is None
            else min(0xFFFFFFFE, max(0, math.ceil(timeout * 1000)))
        )
        try:
            result = self._kernel.WaitForSingleObject(handle, milliseconds)
            error = ctypes.get_last_error()
        finally:
            self._kernel.CloseHandle(handle)
        if result == _WAIT_TIMEOUT:
            assert timeout is not None
            raise subprocess.TimeoutExpired(self.args, timeout)
        if result != 0:
            raise ctypes.WinError(error)
        with self._lock:
            return self._finish()

    def terminate(self) -> None:
        """Terminate the exact owned family, including hung children and grandchildren."""
        with self._lock:
            if self.returncode is not None:
                return
            self._completion.terminate()

    def kill(self) -> None:
        """Use Windows' unconditional family termination for forced shutdown."""
        self.terminate()

    def _finish(self) -> int:
        """Cache the root exit status and close the owner-only family handle."""
        if self.returncode is not None:
            return self.returncode
        code = wintypes.DWORD()
        if not self._kernel.GetExitCodeProcess(self._process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        self._completion.terminate()
        self._completion.wait(5.0)
        deadline = time.monotonic() + 5.0
        accounting = BasicAccounting()
        delay = Event()
        while True:
            if not self._kernel.QueryInformationJobObject(
                self._job,
                1,
                ctypes.byref(accounting),
                ctypes.sizeof(accounting),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if accounting.active_processes == 0:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Process family {self.pid} did not complete kernel termination"
                )
            delay.wait(0.01)
        self.returncode = code.value
        self._release()
        self._job = 0
        self._process = 0
        _LOGGER.info(
            "Released supervised process family | child_pid=%s | exit_code=%s",
            self.pid,
            self.returncode,
        )
        return self.returncode


def _release_handles(kernel: ctypes.WinDLL, job: int, process: int) -> None:
    """Keep the kill-on-close guarantee when an exceptional caller abandons control."""
    kernel.CloseHandle(job)
    kernel.CloseHandle(process)
