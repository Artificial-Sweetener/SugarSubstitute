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

"""Own installation mutation with a crash-reclaimable Windows kernel mutex.

File-lock teardown can lag native process termination. A mutex instead transfers
abandoned ownership through the kernel wait contract. Durable repair journals,
not this adapter, determine how an interrupted installation is recovered.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import errno
import hashlib
import logging
import os
from pathlib import Path
import threading

_LOGGER = logging.getLogger(__name__)
_ACCESS = 0x00100001
_WAIT_ABANDONED = 0x80
_WAIT_TIMEOUT = 258


class _ThreadClaims(threading.local):
    """Reject implicit mutex recursion without retaining dead thread identities."""

    def __init__(self) -> None:
        """Give each live thread its own independently acquired operation names."""
        self.names: set[str] = set()


_CLAIMS = _ThreadClaims()


class _SecurityAttributes(ctypes.Structure):
    """Pass a non-inheritable object descriptor to the native creation boundary."""

    _fields_ = [
        ("length", wintypes.DWORD),
        ("descriptor", ctypes.c_void_p),
        ("inherit", wintypes.BOOL),
    ]


def _kernel_api() -> ctypes.WinDLL:
    """Bind pointer-width-safe mutex operations with explicit Windows error state."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexExW.argtypes = [
        ctypes.POINTER(_SecurityAttributes),
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel.CreateMutexExW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    return kernel


def _create_mutex(kernel: ctypes.WinDLL, name: str) -> int:
    """Share exclusion across sessions/accounts without granting file authority.

    Authenticated users receive only synchronization rights. Installation filesystem
    permissions still govern every mutation; mutex ownership grants no file access.
    The global namespace keeps elevated, ordinary and other-session writers within
    one installation boundary.
    """
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    descriptor = ctypes.c_void_p()
    if not security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        "D:(A;;0x00100001;;;AU)", 1, ctypes.byref(descriptor), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = _SecurityAttributes(
            ctypes.sizeof(_SecurityAttributes), descriptor, False
        )
        handle = kernel.CreateMutexExW(ctypes.byref(attributes), name, 0, _ACCESS)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)
    finally:
        kernel.LocalFree(descriptor)


class WindowsMutationMutex:
    """Retain one non-recursive operation claim until its owning thread releases it."""

    def __init__(self, root: Path) -> None:
        """Acquire immediately or report contention without retaining a handle."""
        identity = os.path.normcase(str(root.resolve())).encode("utf-8")
        self._name = (
            "Global\\SugarSubstitute.Mutation." + hashlib.sha256(identity).hexdigest()
        )
        if self._name in _CLAIMS.names:
            raise BlockingIOError(
                errno.EAGAIN, "An independent operation owns this installation."
            )
        self._kernel = _kernel_api()
        self._thread = threading.current_thread()
        self._handle: int | None = _create_mutex(self._kernel, self._name)
        result = int(self._kernel.WaitForSingleObject(self._handle, 0))
        if result not in {0, _WAIT_ABANDONED}:
            error = ctypes.get_last_error()
            self._kernel.CloseHandle(self._handle)
            self._handle = None
            if result == _WAIT_TIMEOUT:
                raise BlockingIOError(errno.EAGAIN, "Installation mutation is active.")
            raise ctypes.WinError(error)
        _CLAIMS.names.add(self._name)
        if result == _WAIT_ABANDONED:
            _LOGGER.info(
                "Acquired abandoned installation mutation ownership",
                extra={"operation": "installation_mutation"},
            )

    def release(self) -> None:
        """Release exactly once from the native owner before closing its handle."""
        if self._handle is None or threading.current_thread() is not self._thread:
            raise RuntimeError(
                "Mutation mutex release requires its live owning thread."
            )
        if not self._kernel.ReleaseMutex(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())
        handle, self._handle = self._handle, None
        _CLAIMS.names.remove(self._name)
        if not self._kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
