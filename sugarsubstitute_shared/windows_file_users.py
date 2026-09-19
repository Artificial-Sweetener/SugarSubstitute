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

"""Query Windows resource users as evidence for separately authorized recovery.

Restart Manager reports file users, including ordinary readers. This adapter
neither identifies exclusive lock authority nor shuts down any process.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path

from sugarsubstitute_shared.process_identity import ProcessIdentity

_LOGGER = logging.getLogger(__name__)
_MAXIMUM_FILE_USERS = 1024
_ERROR_MORE_DATA = 234


class _UniqueProcess(ctypes.Structure):
    """Match the Restart Manager process-incarnation ABI."""

    _fields_ = [("pid", wintypes.DWORD), ("started", wintypes.FILETIME)]


class _ProcessInfo(ctypes.Structure):
    """Match the documented Restart Manager resource-user record."""

    _fields_ = [
        ("process", _UniqueProcess),
        ("application_name", wintypes.WCHAR * 256),
        ("service_name", wintypes.WCHAR * 64),
        ("application_type", ctypes.c_int),
        ("application_status", wintypes.ULONG),
        ("session_id", wintypes.DWORD),
        ("restartable", wintypes.BOOL),
    ]


class WindowsFileUsers:
    """Own a read-only resource-user query with bounded allocation and session cleanup."""

    def __init__(self) -> None:
        """Declare the native ABI without registering or stopping any application."""
        self._api = ctypes.WinDLL("Rstrtmgr.dll")
        self._api.RmStartSession.argtypes = [
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD,
            wintypes.LPWSTR,
        ]
        self._api.RmStartSession.restype = wintypes.DWORD
        self._api.RmRegisterResources.argtypes = [
            wintypes.DWORD,
            wintypes.UINT,
            ctypes.POINTER(wintypes.LPCWSTR),
            wintypes.UINT,
            ctypes.POINTER(_UniqueProcess),
            wintypes.UINT,
            ctypes.POINTER(wintypes.LPCWSTR),
        ]
        self._api.RmRegisterResources.restype = wintypes.DWORD
        self._api.RmGetList.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(wintypes.UINT),
            ctypes.POINTER(wintypes.UINT),
            ctypes.POINTER(_ProcessInfo),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._api.RmGetList.restype = wintypes.DWORD
        self._api.RmEndSession.argtypes = [wintypes.DWORD]
        self._api.RmEndSession.restype = wintypes.DWORD

    def snapshot(self, path: Path) -> tuple[ProcessIdentity, ...]:
        """Inspect only the supplied resource; call away from the GUI event loop.

        The native service owns its request deadline. Callers that need a strict
        wall-clock deadline must execute this query in their supervised worker.
        """
        session = wintypes.DWORD()
        key = ctypes.create_unicode_buffer(33)
        _require_success(int(self._api.RmStartSession(ctypes.byref(session), 0, key)))
        try:
            resources = (wintypes.LPCWSTR * 1)(str(path.resolve()))
            _require_success(
                int(
                    self._api.RmRegisterResources(
                        session, 1, resources, 0, None, 0, None
                    )
                )
            )
            return self._read_users(session)
        finally:
            error = int(self._api.RmEndSession(session))
            if error:
                _LOGGER.warning(
                    "Could not close Windows file-user inspection session",
                    extra={"native_error": error},
                )

    def _read_users(self, session: wintypes.DWORD) -> tuple[ProcessIdentity, ...]:
        """Bound allocations and fail explicitly if the native snapshot keeps changing."""
        capacity = 16
        for _attempt in range(3):
            records = (_ProcessInfo * capacity)()
            needed = wintypes.UINT()
            received = wintypes.UINT(capacity)
            reboot_reason = wintypes.DWORD()
            error = int(
                self._api.RmGetList(
                    session,
                    ctypes.byref(needed),
                    ctypes.byref(received),
                    records,
                    ctypes.byref(reboot_reason),
                )
            )
            if error == _ERROR_MORE_DATA:
                capacity = max(capacity + 1, int(needed.value))
                if capacity > _MAXIMUM_FILE_USERS:
                    raise OSError("Windows resource-user snapshot exceeds its bound.")
                continue
            _require_success(error)
            if received.value > capacity:
                raise OSError("Windows returned an invalid resource-user count.")
            users: list[ProcessIdentity] = []
            for record in records[: received.value]:
                started = record.process.started
                ticks = (int(started.dwHighDateTime) << 32) | int(started.dwLowDateTime)
                users.append(
                    ProcessIdentity(
                        int(record.process.pid), (ticks - 116444736000000000) / 10000000
                    )
                )
            return tuple(users)
        raise OSError("Windows resource-user snapshot changed during inspection.")


def _require_success(error: int) -> None:
    """Preserve the native failure code for the recovery controller's diagnostics."""
    if error:
        raise ctypes.WinError(error)
