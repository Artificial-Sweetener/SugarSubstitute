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

"""Seal an owned job and wait for its retained members to finish native exit."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import time
import weakref

from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_job_api import ExtendedLimits, load_kernel


class WindowsJobCompletion:
    """Own the native exit barrier for one borrowed, exclusively managed job.

    Job accounting can reach zero before process handles become signaled. Seal
    admission before retaining members, then wait on their process objects rather
    than treating that accounting update as completed resource teardown.
    """

    def __init__(self, job: int) -> None:
        """Keep retained references non-inheritable and scoped to this supervisor."""
        self._job = job
        self._kernel = load_kernel()
        self._native = NativeProcessHandleApi()
        self._members: list[int] = []
        self._sealed = False
        self._release = weakref.finalize(
            self, _close_members, self._native, self._members
        )

    def terminate(self) -> None:
        """Close job admission and retain live members before requesting termination."""
        if not self._sealed:
            limits = ExtendedLimits()
            if not self._kernel.QueryInformationJobObject(
                self._job, 9, ctypes.byref(limits), ctypes.sizeof(limits), None
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            limits.basic.flags |= 0x8
            limits.basic.active_process_limit = 0
            if not self._kernel.SetInformationJobObject(
                self._job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            self._retain_members()
            self._sealed = True
        if not self._kernel.TerminateJobObject(self._job, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, timeout: float) -> None:
        """Require native exit for every retained member within one shared deadline."""
        if not self._sealed:
            raise RuntimeError("Job completion requires closed process admission.")
        deadline = time.monotonic() + timeout
        for handle in self._members:
            remaining = max(0, math.ceil((deadline - time.monotonic()) * 1000))
            if not self._native.wait(handle, remaining):
                raise TimeoutError(
                    "A supervised job member has not completed native exit."
                )
        self._release()

    def _retain_members(self) -> None:
        """Retain only members of this job, excluding any PID reused during enumeration."""
        capacity = 16
        while True:
            buffer = ctypes.create_string_buffer(
                8 + ctypes.sizeof(ctypes.c_size_t) * capacity
            )
            if self._kernel.QueryInformationJobObject(
                self._job, 3, buffer, ctypes.sizeof(buffer), None
            ):
                break
            error = ctypes.get_last_error()
            if error != 234:
                raise ctypes.WinError(error)
            capacity = max(capacity * 2, wintypes.DWORD.from_buffer(buffer).value)
        count = wintypes.DWORD.from_buffer(buffer, 4).value
        for index in range(count):
            pid = ctypes.c_size_t.from_buffer(
                buffer, 8 + index * ctypes.sizeof(ctypes.c_size_t)
            ).value
            handle = self._native.open(pid)
            if handle is None:
                continue
            retained = False
            try:
                member = wintypes.BOOL()
                if not self._kernel.IsProcessInJob(
                    handle, self._job, ctypes.byref(member)
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                if member.value:
                    self._members.append(handle)
                    retained = True
            finally:
                if not retained:
                    self._native.close(handle)


def _close_members(native: NativeProcessHandleApi, members: list[int]) -> None:
    """Release retained process references on verified completion or owner disposal."""
    while members:
        native.close(members.pop())
