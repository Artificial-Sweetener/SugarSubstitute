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

"""Own bounded real-Node execution for tests across concurrent pytest workers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys

_NODE_PROCESS_MUTEX_NAME = "Local\\SugarSubstitute-Test-Node-Runtime"
_NODE_PROCESS_MUTEX_WAIT_MILLISECONDS = 120_000
_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102


class NodeProcessCapacityError(RuntimeError):
    """Report failure to acquire the bounded real-Node execution capacity."""


def run_node(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float = 30.0,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one real Node command through the platform's stable capacity owner."""

    command = ["node", *arguments]
    with node_process_capacity():
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=check,
        )


@contextmanager
def node_process_capacity(
    *,
    wait_milliseconds: int = _NODE_PROCESS_MUTEX_WAIT_MILLISECONDS,
) -> Iterator[None]:
    """Serialize real Node startup only where Windows runner evidence requires it."""

    if sys.platform != "win32":
        yield
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.CreateMutexW(None, False, _NODE_PROCESS_MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    owns_mutex = False
    try:
        wait_result = int(kernel32.WaitForSingleObject(handle, wait_milliseconds))
        if wait_result == _WAIT_TIMEOUT:
            raise NodeProcessCapacityError(
                "Timed out waiting for the shared Windows Node runtime capacity."
            )
        if wait_result not in {_WAIT_OBJECT_0, _WAIT_ABANDONED}:
            raise ctypes.WinError(ctypes.get_last_error())
        owns_mutex = True
        yield
    finally:
        if owns_mutex and not kernel32.ReleaseMutex(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


__all__ = ["NodeProcessCapacityError", "node_process_capacity", "run_node"]
