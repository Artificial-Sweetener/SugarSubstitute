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

"""Serialize launcher log records written by independent processes."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self, cast


class _ProcessLock(Protocol):
    """Describe a crash-releasing operating-system process lock."""

    def __enter__(self) -> Self:
        """Acquire exclusive write ownership."""

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release exclusive write ownership."""

    def close(self) -> None:
        """Release native resources owned by this process."""


class InterprocessFileHandler(logging.FileHandler):
    """Write complete log records under one native cross-process lock."""

    def __init__(self, filename: Path, *, encoding: str) -> None:
        """Open the destination and its crash-releasing native lock."""

        super().__init__(filename, encoding=encoding)
        self._process_lock = _build_process_lock(filename, self)

    def emit(self, record: logging.LogRecord) -> None:
        """Serialize formatting, append, and flush as one process operation."""

        with self._process_lock:
            super().emit(record)

    def close(self) -> None:
        """Close the stream before releasing its native lock resource."""

        try:
            super().close()
        finally:
            process_lock = getattr(self, "_process_lock", None)
            if process_lock is not None:
                process_lock.close()


class _WindowsNamedMutex:
    """Serialize writes with a session-local mutex reclaimed after a crash."""

    _WAIT_OBJECT_0 = 0
    _WAIT_ABANDONED = 0x80
    _INFINITE = 0xFFFFFFFF

    def __init__(self, name: str) -> None:
        """Create or open the process-shared mutex with the default user ACL."""

        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._ctypes = ctypes
        self._kernel32 = kernel32
        self._handle = handle

    def __enter__(self) -> Self:
        """Wait for exclusive ownership, accepting crash-abandoned ownership."""

        result = int(self._kernel32.WaitForSingleObject(self._handle, self._INFINITE))
        if result not in (self._WAIT_OBJECT_0, self._WAIT_ABANDONED):
            raise self._ctypes.WinError(self._ctypes.get_last_error())
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the mutex after the complete record reaches disk."""

        _ = exception_type, exception, traceback
        if not self._kernel32.ReleaseMutex(self._handle):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def close(self) -> None:
        """Close this process's mutex handle without affecting other writers."""

        handle = self._handle
        if handle is None:
            return
        self._handle = None
        if not self._kernel32.CloseHandle(handle):
            raise self._ctypes.WinError(self._ctypes.get_last_error())


class _PosixAdvisoryLock:
    """Serialize writes through the destination file's advisory lock."""

    def __init__(self, handler: logging.FileHandler) -> None:
        """Retain the handler whose active stream owns the lock."""

        self._handler = handler

    def __enter__(self) -> Self:
        """Acquire the destination file's exclusive advisory lock."""

        fcntl = _posix_fcntl()
        stream = self._handler.stream
        if stream is None:
            stream = self._handler._open()
            self._handler.stream = stream
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the destination file's advisory lock."""

        fcntl = _posix_fcntl()
        _ = exception_type, exception, traceback
        stream = self._handler.stream
        if stream is not None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def close(self) -> None:
        """Leave stream cleanup to the owning logging handler."""


def _build_process_lock(
    path: Path,
    handler: logging.FileHandler,
) -> _ProcessLock:
    """Return the native lock appropriate for the running platform."""

    if os.name != "nt":
        return _PosixAdvisoryLock(handler)
    normalized = os.path.normcase(os.path.abspath(path))
    identity = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return _WindowsNamedMutex(f"Local\\SugarSubstitute.LauncherLog.{identity}")


def _posix_fcntl() -> Any:
    """Import the POSIX-only lock API behind the runtime platform boundary."""

    import importlib

    return cast(Any, importlib.import_module("fcntl"))


__all__ = ["InterprocessFileHandler"]
