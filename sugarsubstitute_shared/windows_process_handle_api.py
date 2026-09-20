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

"""Declare retained Windows process handle operations and explicit access rights."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class NativeProcessHandleApi:
    """Own the Windows ABI for retained process identity and lifetime operations."""

    def __init__(self, *, allow_termination: bool = False) -> None:
        """Declare pointer-safe native signatures without process-global mutation."""
        self._access = 0x1000 | 0x00100000 | (0x0001 if allow_termination else 0)
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self._kernel.OpenProcess.restype = wintypes.HANDLE
        self._kernel.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            *([ctypes.POINTER(wintypes.FILETIME)] * 4),
        ]
        self._kernel.GetProcessTimes.restype = wintypes.BOOL
        self._kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel.CloseHandle.restype = wintypes.BOOL
        self._kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self._kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel.TerminateProcess.restype = wintypes.BOOL

    def open(self, pid: int) -> int | None:
        """Acquire only the lifetime rights requested by this adapter owner."""
        handle = self._kernel.OpenProcess(self._access, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return None
            raise ctypes.WinError(error)
        return int(handle)

    def creation_time(self, handle: int) -> float:
        """Convert this retained process's FILETIME to Unix seconds."""
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not self._kernel.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return (ticks - 116444736000000000) / 10000000

    def wait(self, handle: int, milliseconds: int) -> bool:
        """Wait on the already verified object even if its PID is later recycled."""
        result = self._kernel.WaitForSingleObject(handle, milliseconds)
        if result == 0:
            return True
        if result == 258:
            return False
        raise ctypes.WinError(ctypes.get_last_error())

    def close(self, handle: int) -> None:
        """Release a process reference on success, mismatch, timeout or failure."""
        if not self._kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def image_path(self, handle: int) -> Path:
        """Read the executable image from the retained process object."""
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not self._kernel.QueryFullProcessImageNameW(
            handle, 0, image, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(image.value)

    def exit_code(self, handle: int) -> int:
        """Return the completed process's native exit code."""

        code = wintypes.DWORD()
        if not self._kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(code.value)

    def terminate(self, handle: int) -> None:
        """End only the retained object, accepting an already completed exit."""
        if not self._kernel.TerminateProcess(handle, 1):
            error = ctypes.get_last_error()
            if self.wait(handle, 0):
                return
            raise ctypes.WinError(error)
