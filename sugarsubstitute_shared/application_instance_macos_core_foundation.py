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

"""Adapt Core Foundation message-port primitives for application IPC."""

from __future__ import annotations

import ctypes
import ctypes.util
from dataclasses import dataclass


UTF8_ENCODING = 0x08000100

MessagePortCallback = ctypes.CFUNCTYPE(
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int32,
    ctypes.c_void_p,
    ctypes.c_void_p,
)


@dataclass(frozen=True, slots=True)
class LocalMessagePortCreation:
    """Describe whether Core Foundation created or returned a named local port."""

    port: int
    created: bool


class MessagePortContext(ctypes.Structure):
    """Describe the Core Foundation callback context ABI."""

    _fields_ = [
        ("version", ctypes.c_long),
        ("info", ctypes.c_void_p),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("copy_description", ctypes.c_void_p),
    ]


class CoreFoundationMessagePortApi:
    """Expose typed Core Foundation operations used by the macOS transport."""

    def __init__(self) -> None:
        """Load and configure the system Core Foundation framework."""

        framework_path = ctypes.util.find_library("CoreFoundation")
        if framework_path is None:
            raise RuntimeError("CoreFoundation is unavailable on macOS.")
        self._core_foundation = ctypes.CDLL(framework_path)
        self._configure()

    def create_name(self, value: str) -> int:
        """Create one retained Core Foundation string."""

        name = self._core_foundation.CFStringCreateWithCString(
            None,
            value.encode("utf-8"),
            UTF8_ENCODING,
        )
        if not name:
            raise RuntimeError("Could not allocate the macOS instance-port name.")
        return int(name)

    def create_local_port(
        self,
        name: int,
        callback: object,
        context: MessagePortContext,
    ) -> LocalMessagePortCreation:
        """Atomically claim one named port and expose duplicate-name results."""

        should_free_info = ctypes.c_bool(False)
        port = self._core_foundation.CFMessagePortCreateLocal(
            None,
            name,
            callback,
            ctypes.byref(context),
            ctypes.byref(should_free_info),
        )
        return LocalMessagePortCreation(
            port=int(port) if port else 0,
            created=bool(port) and not should_free_info.value,
        )

    def invalidate_port(self, port: int) -> None:
        """Invalidate one local message port before release."""

        self._core_foundation.CFMessagePortInvalidate(port)

    def release(self, value: int) -> None:
        """Release one retained Core Foundation object."""

        self._core_foundation.CFRelease(value)

    def _configure(self) -> None:
        """Declare every Core Foundation signature used by this adapter."""

        library = self._core_foundation
        library.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        library.CFStringCreateWithCString.restype = ctypes.c_void_p
        library.CFMessagePortCreateLocal.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            MessagePortCallback,
            ctypes.POINTER(MessagePortContext),
            ctypes.POINTER(ctypes.c_bool),
        ]
        library.CFMessagePortCreateLocal.restype = ctypes.c_void_p
        library.CFMessagePortInvalidate.argtypes = [ctypes.c_void_p]
        library.CFMessagePortInvalidate.restype = None
        library.CFRelease.argtypes = [ctypes.c_void_p]
        library.CFRelease.restype = None


__all__ = [
    "CoreFoundationMessagePortApi",
    "LocalMessagePortCreation",
    "MessagePortCallback",
    "MessagePortContext",
]
