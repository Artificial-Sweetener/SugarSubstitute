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

"""Inspect and retire the native job that owns a managed Windows backend family."""

from __future__ import annotations

from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
from types import TracebackType

from sugarsubstitute_shared.windows_job_completion import WindowsJobCompletion
from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_job_api import BasicAccounting, load_kernel


class WindowsManagedJob(AbstractContextManager["WindowsManagedJob"]):
    """Retain one kernel family independently of recycled root or listener PIDs."""

    def __init__(self, handle: int, kernel: ctypes.WinDLL) -> None:
        """Own the acquired reference without taking the original launcher's handle."""
        self._handle = handle
        self._kernel = kernel

    @classmethod
    def open(
        cls, name: str, *, for_termination: bool = False
    ) -> WindowsManagedJob | None:
        """Open the recorded family; an absent kill-on-close job has already retired."""
        if not name:
            raise ValueError("Managed Windows job identity is missing.")
        kernel = load_kernel()
        access = 0x0004 | (0x0002 | 0x0008 if for_termination else 0)
        handle = kernel.OpenJobObjectW(access, False, name)
        if not handle:
            error = ctypes.get_last_error()
            if error == 2:
                return None
            raise ctypes.WinError(error)
        return cls(int(handle), kernel)

    def contains_process(self, pid: int) -> bool:
        """Ask Windows about a retained process object rather than matching a PID."""
        native = NativeProcessHandleApi()
        process = native.open(pid)
        if process is None:
            return False
        try:
            member = wintypes.BOOL()
            if not self._kernel.IsProcessInJob(
                process, self._handle, ctypes.byref(member)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return bool(member.value)
        finally:
            native.close(process)

    def has_members(self) -> bool:
        """Detect an owned family even after its original root process has exited."""
        accounting = BasicAccounting()
        if not self._kernel.QueryInformationJobObject(
            self._handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(accounting.active_processes)

    def terminate_and_wait(self, *, timeout_seconds: float) -> None:
        """Seal and retire the complete family through the shared native exit barrier."""
        completion = WindowsJobCompletion(self._handle)
        completion.terminate()
        completion.wait(timeout_seconds)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release this reference after observation or verified family termination."""
        if not self._kernel.CloseHandle(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())
