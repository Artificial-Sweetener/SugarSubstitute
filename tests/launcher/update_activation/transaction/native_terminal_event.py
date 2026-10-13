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

"""Own a unique native event for headless terminal-process coordination."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class TerminalEvent:
    """Retain one event handle and release it deterministically."""

    def __init__(self, name: str, *, create: bool) -> None:
        """Create a parent barrier or open its child-side wait handle."""
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create_event = self._kernel.CreateEventW
        create_event.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        create_event.restype = wintypes.HANDLE
        open_event = self._kernel.OpenEventW
        open_event.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
        open_event.restype = wintypes.HANDLE
        self._kernel.SetEvent.argtypes = (wintypes.HANDLE,)
        self._kernel.SetEvent.restype = wintypes.BOOL
        self._kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self._kernel.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel.CloseHandle.restype = wintypes.BOOL
        self._handle = (
            create_event(None, False, False, name)
            if create
            else open_event(0x00100000, False, name)
        )
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def signal(self) -> None:
        """Release the child only after production readiness has been accepted."""
        if not self._kernel.SetEvent(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, *, timeout: float) -> None:
        """Bound failure diagnosis while waiting for the real parent barrier."""
        if self._kernel.WaitForSingleObject(self._handle, int(timeout * 1000)) != 0:
            raise TimeoutError("Native terminal event was not signaled")

    def close(self) -> None:
        """Release exactly this test-owned event handle."""
        if not self._kernel.CloseHandle(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())
