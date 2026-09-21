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

"""Synchronize destructive child-process qualification on observable state."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import uuid

from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)


WAITING_EVENT_ENV = "SUGAR_SUBSTITUTE_QUALIFY_WAITING_EVENT"
_EVENT_MODIFY_STATE = 0x0002
_EVENT_WAIT_MILLISECONDS = 10_000
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102

ProcessStarter = Callable[
    [Sequence[str], Mapping[str, str]],
    tuple[ChildProcess, Path],
]


class _WindowsEventApi:
    """Own the native named-event calls used for exact cross-process state."""

    def __init__(self) -> None:
        """Bind the small kernel32 event surface with explicit ctypes contracts."""

        if sys.platform != "win32":
            raise RuntimeError("Crash qualification named events require Windows.")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateEventW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.OpenEventW.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.OpenEventW.restype = wintypes.HANDLE
        kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32

    def create(self, name: str) -> int:
        """Create one manual-reset event owned by the parent test process."""

        handle = self._kernel32.CreateEventW(None, True, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    def open_for_signal(self, name: str) -> int:
        """Open the parent event with only the right needed to signal it."""

        handle = self._kernel32.OpenEventW(_EVENT_MODIFY_STATE, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    def signal(self, handle: int) -> None:
        """Signal that the child reached its observable waiting state."""

        if not self._kernel32.SetEvent(wintypes.HANDLE(handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, handle: int) -> int:
        """Wait once for child state with a bounded deadlock failure."""

        return int(
            self._kernel32.WaitForSingleObject(
                wintypes.HANDLE(handle),
                _EVENT_WAIT_MILLISECONDS,
            )
        )

    def close(self, handle: int) -> None:
        """Release this process's named-event handle."""

        if not self._kernel32.CloseHandle(wintypes.HANDLE(handle)):
            raise ctypes.WinError(ctypes.get_last_error())


def controlled_expiry_clock() -> Callable[[], float]:
    """Return a clock that expires only after readiness establishes its deadline."""

    deadline_established = False

    def monotonic() -> float:
        """Hold time for deadline creation, then advance beyond the test timeout."""

        nonlocal deadline_established
        if not deadline_established:
            deadline_established = True
            return 0.0
        return 1.0

    return monotonic


def publish_waiting_event() -> None:
    """Signal that the fault child flushed diagnostics and is safe to terminate."""

    event_name = os.environ.get(WAITING_EVENT_ENV)
    if event_name is None:
        return
    event_api = _WindowsEventApi()
    handle = event_api.open_for_signal(event_name)
    try:
        event_api.signal(handle)
    finally:
        event_api.close(handle)


def synchronized_process_starter() -> ProcessStarter:
    """Return a real starter that yields after an exact child-process signal."""

    def start(
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[ChildProcess, Path]:
        """Start the child and wait once for its observable waiting state."""

        event_api = _WindowsEventApi()
        event_name = f"Local\\SugarSubstitute-CrashQualification-{uuid.uuid4()}"
        event_handle = event_api.create(event_name)
        try:
            process, startup_log_path = spawn_supervised_process(
                command,
                environment={**environment, WAITING_EVENT_ENV: event_name},
            )
            wait_result = event_api.wait(event_handle)
            if wait_result == _WAIT_TIMEOUT:
                _stop_process(process)
                raise AssertionError(
                    "Qualification child did not signal its waiting state within "
                    f"{_EVENT_WAIT_MILLISECONDS / 1_000:g} seconds: "
                    f"log={startup_log_path}"
                )
            if wait_result != _WAIT_OBJECT_0:
                _stop_process(process)
                raise ctypes.WinError(ctypes.get_last_error())
            return process, startup_log_path
        finally:
            event_api.close(event_handle)

    return start


def _stop_process(process: ChildProcess) -> None:
    """Stop a child retained only because qualification synchronization failed."""

    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


__all__ = [
    "ProcessStarter",
    "WAITING_EVENT_ENV",
    "controlled_expiry_clock",
    "publish_waiting_event",
    "synchronized_process_starter",
]
