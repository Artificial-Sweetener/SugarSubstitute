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
import os
from pathlib import Path
import subprocess
from threading import Event, RLock
import time
import weakref

from sugarsubstitute_shared.windows_process_job_api import (
    ExtendedLimits,
    BasicAccounting,
    ProcessInformation,
    StartupInfoEx,
    load_kernel,
)
from sugarsubstitute_shared.windows_job_completion import WindowsJobCompletion

_LOGGER = logging.getLogger(__name__)
_KILL_ON_JOB_CLOSE = 0x2000
_ALLOW_EXPLICIT_BREAKAWAY = 0x0800
_HANDLE_LIST_ATTRIBUTE = 0x00020002
_JOB_LIST_ATTRIBUTE = 0x0002000D
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NO_WINDOW = 0x08000000
_STARTF_USESTDHANDLES = 0x00000100
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
        import msvcrt

        if not command or any("\0" in argument for argument in command):
            raise ValueError("A process command must contain valid arguments.")
        if any(
            not key or "=" in key or "\0" in key or "\0" in value
            for key, value in environment.items()
        ):
            raise ValueError(
                "A process environment must contain valid names and values."
            )
        kernel = load_kernel()
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = _KILL_ON_JOB_CLOSE
        if allow_breakaway:
            limits.basic.flags |= _ALLOW_EXPLICIT_BREAKAWAY
        handles: list[int] = []
        attributes_initialized = False
        size = ctypes.c_size_t()
        attributes = None
        try:
            if not kernel.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
            if not size.value:
                raise ctypes.WinError(ctypes.get_last_error())
            attributes = ctypes.create_string_buffer(size.value)
            if not kernel.InitializeProcThreadAttributeList(
                attributes, 2, 0, ctypes.byref(size)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            attributes_initialized = True
            with open(os.devnull, "rb") as null_input:
                for fd in (
                    null_input.fileno(),
                    output_fd,
                    output_fd if error_fd is None else error_fd,
                ):
                    duplicate = wintypes.HANDLE()
                    current_process = kernel.GetCurrentProcess()
                    if not kernel.DuplicateHandle(
                        current_process,
                        msvcrt.get_osfhandle(fd),
                        current_process,
                        ctypes.byref(duplicate),
                        0,
                        True,
                        2,
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                    assert duplicate.value is not None
                    handles.append(duplicate.value)
                inherited = (wintypes.HANDLE * len(handles))(*handles)
                jobs = (wintypes.HANDLE * 1)(job)
                for key, values in (
                    (_HANDLE_LIST_ATTRIBUTE, inherited),
                    (_JOB_LIST_ATTRIBUTE, jobs),
                ):
                    if not kernel.UpdateProcThreadAttribute(
                        attributes,
                        0,
                        key,
                        ctypes.byref(values),
                        ctypes.sizeof(values),
                        None,
                        None,
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                startup = StartupInfoEx()
                startup.startup.size = ctypes.sizeof(startup)
                startup.startup.flags = _STARTF_USESTDHANDLES
                startup.startup.stdin = handles[0]
                startup.startup.stdout = handles[1]
                startup.startup.stderr = handles[2]
                startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
                process_info = ProcessInformation()
                environment_block = ctypes.create_unicode_buffer(
                    "\0".join(
                        f"{key}={value}"
                        for key, value in sorted(
                            environment.items(), key=lambda item: item[0].upper()
                        )
                    )
                    + "\0"
                )
                command_line = ctypes.create_unicode_buffer(
                    subprocess.list2cmdline(command)
                )
                if not kernel.CreateProcessW(
                    command[0],
                    command_line,
                    None,
                    None,
                    True,
                    _EXTENDED_STARTUPINFO_PRESENT
                    | _CREATE_UNICODE_ENVIRONMENT
                    | _CREATE_NO_WINDOW,
                    environment_block,
                    str(cwd) if cwd is not None else None,
                    ctypes.byref(startup),
                    ctypes.byref(process_info),
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
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
            if attributes_initialized:
                kernel.DeleteProcThreadAttributeList(attributes)
            for handle in handles:
                kernel.CloseHandle(handle)
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
