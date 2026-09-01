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
MAXIMUM_MESSAGE_BYTES = 1024 * 1024

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

    def create_remote_port(self, name: int) -> int:
        """Connect to one named local message port in this bootstrap session."""

        port = self._core_foundation.CFMessagePortCreateRemote(None, name)
        return int(port) if port else 0

    def create_run_loop_source(self, port: int) -> int:
        """Create one retained run-loop source for a local message port."""

        source = self._core_foundation.CFMessagePortCreateRunLoopSource(None, port, 0)
        return int(source) if source else 0

    def current_run_loop(self) -> int:
        """Return this thread's Core Foundation run loop."""

        run_loop = self._core_foundation.CFRunLoopGetCurrent()
        if not run_loop:
            raise RuntimeError("Core Foundation did not provide a current run loop.")
        return int(run_loop)

    def default_run_loop_mode(self) -> int:
        """Return the system default run-loop mode constant."""

        mode = ctypes.c_void_p.in_dll(
            self._core_foundation,
            "kCFRunLoopDefaultMode",
        ).value
        if mode is None:
            raise RuntimeError("Core Foundation default run-loop mode is unavailable.")
        return int(mode)

    def add_run_loop_source(self, run_loop: int, source: int, mode: int) -> None:
        """Attach one source to a run loop."""

        self._core_foundation.CFRunLoopAddSource(run_loop, source, mode)

    def remove_run_loop_source(self, run_loop: int, source: int, mode: int) -> None:
        """Detach one source from a run loop."""

        self._core_foundation.CFRunLoopRemoveSource(run_loop, source, mode)

    def run_current_loop(self) -> None:
        """Serve the current Core Foundation run loop until stopped."""

        self._core_foundation.CFRunLoopRun()

    def stop_run_loop(self, run_loop: int) -> None:
        """Stop and wake a service run loop."""

        self._core_foundation.CFRunLoopStop(run_loop)
        self._core_foundation.CFRunLoopWakeUp(run_loop)

    def invalidate_port(self, port: int) -> None:
        """Invalidate one local message port before release."""

        self._core_foundation.CFMessagePortInvalidate(port)

    def send_request(
        self,
        port: int,
        message_identifier: int,
        data: int,
        timeout_seconds: float,
    ) -> tuple[int, int]:
        """Send one synchronous native request and return its retained response."""

        response = ctypes.c_void_p()
        status = self._core_foundation.CFMessagePortSendRequest(
            port,
            message_identifier,
            data,
            timeout_seconds,
            timeout_seconds,
            self.default_run_loop_mode(),
            ctypes.byref(response),
        )
        return int(status), int(response.value) if response.value else 0

    def create_data(self, payload: bytes) -> int:
        """Create one retained Core Foundation data value from bytes."""

        buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        data = self._core_foundation.CFDataCreate(None, buffer, len(payload))
        if not data:
            raise RuntimeError("Could not allocate a Core Foundation message payload.")
        return int(data)

    def read_data(self, data: int) -> bytes:
        """Copy one Core Foundation data value into Python-owned bytes."""

        length = int(self._core_foundation.CFDataGetLength(data))
        if length < 0 or length > MAXIMUM_MESSAGE_BYTES:
            raise ValueError("Application instance message exceeds its size limit.")
        pointer = self._core_foundation.CFDataGetBytePtr(data)
        if length and not pointer:
            raise ValueError("Application instance message has no payload bytes.")
        return ctypes.string_at(pointer, length)

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
        library.CFMessagePortCreateRemote.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        library.CFMessagePortCreateRemote.restype = ctypes.c_void_p
        library.CFMessagePortCreateRunLoopSource.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
        ]
        library.CFMessagePortCreateRunLoopSource.restype = ctypes.c_void_p
        library.CFMessagePortSendRequest.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.CFMessagePortSendRequest.restype = ctypes.c_int32
        library.CFMessagePortInvalidate.argtypes = [ctypes.c_void_p]
        library.CFMessagePortInvalidate.restype = None
        library.CFRunLoopGetCurrent.argtypes = []
        library.CFRunLoopGetCurrent.restype = ctypes.c_void_p
        library.CFRunLoopAddSource.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        library.CFRunLoopAddSource.restype = None
        library.CFRunLoopRemoveSource.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        library.CFRunLoopRemoveSource.restype = None
        library.CFRunLoopRun.argtypes = []
        library.CFRunLoopRun.restype = None
        library.CFRunLoopStop.argtypes = [ctypes.c_void_p]
        library.CFRunLoopStop.restype = None
        library.CFRunLoopWakeUp.argtypes = [ctypes.c_void_p]
        library.CFRunLoopWakeUp.restype = None
        library.CFDataCreate.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_long,
        ]
        library.CFDataCreate.restype = ctypes.c_void_p
        library.CFDataGetLength.argtypes = [ctypes.c_void_p]
        library.CFDataGetLength.restype = ctypes.c_long
        library.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
        library.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_ubyte)
        library.CFRelease.argtypes = [ctypes.c_void_p]
        library.CFRelease.restype = None


__all__ = [
    "CoreFoundationMessagePortApi",
    "LocalMessagePortCreation",
    "MAXIMUM_MESSAGE_BYTES",
    "MessagePortCallback",
    "MessagePortContext",
]
