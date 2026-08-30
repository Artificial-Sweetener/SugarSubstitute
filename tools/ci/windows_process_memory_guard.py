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

"""Bound Windows pytest worker memory before a runaway process exhausts CI."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import faulthandler
import os
import sys
import threading
import time

_memory_guard_started = False


class _ProcessMemoryCountersEx(ctypes.Structure):
    """Represent the Windows process memory counters returned by psapi."""

    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("PageFaultCount", ctypes.wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def start_windows_process_memory_guard(
    *,
    limit_bytes: int,
    check_interval_seconds: float,
) -> None:
    """Start one daemon memory guard in each applicable pytest process."""

    global _memory_guard_started
    if _memory_guard_started or sys.platform != "win32" or limit_bytes <= 0:
        return

    _memory_guard_started = True
    thread = threading.Thread(
        target=_watch_process_memory,
        args=(limit_bytes, check_interval_seconds),
        name="substitute-test-memory-guard",
        daemon=True,
    )
    thread.start()


def _watch_process_memory(limit_bytes: int, interval_seconds: float) -> None:
    """Terminate this process if private memory exceeds the configured limit."""

    while True:
        private_bytes = _current_process_private_bytes()
        if private_bytes is not None and private_bytes > limit_bytes:
            print(
                (
                    "Substitute pytest process exceeded memory limit: "
                    f"{private_bytes / 1024**3:.2f} GiB used, "
                    f"{limit_bytes / 1024**3:.2f} GiB allowed. "
                    "Terminating this test process."
                ),
                file=sys.stderr,
                flush=True,
            )
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
            os._exit(137)
        time.sleep(max(interval_seconds, 0.1))


def _current_process_private_bytes() -> int | None:
    """Return private bytes for the current Windows process."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        ctypes.wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(_ProcessMemoryCountersEx)
    process = kernel32.GetCurrentProcess()
    succeeded = psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    if not succeeded:
        return None
    return int(counters.PrivateUsage)


__all__ = ["start_windows_process_memory_guard"]
