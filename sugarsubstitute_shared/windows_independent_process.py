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

"""Admit independent Windows handoffs before their first instruction executes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
from ctypes import wintypes
import errno
import logging
from pathlib import Path
import subprocess

from sugarsubstitute_shared.windows_process_creation import create_windows_process
from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_job_api import load_kernel

_LOGGER = logging.getLogger(__name__)


def start_independent_windows_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
    output_fd: int,
) -> int:
    """Resume only a child proven independent of every inherited job.

    Nested jobs may accept CREATE_BREAKAWAY_FROM_JOB while retaining the child
    in an outer job. Suspend creation, inspect the actual child, then either
    resume it or retire it before it can spawn descendants or change files.
    """
    kernel = load_kernel()
    kernel.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    process = create_windows_process(
        command,
        environment=environment,
        cwd=cwd,
        output_fd=output_fd,
        creation_flags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_BREAKAWAY_FROM_JOB
            | 0x00000004
        ),
    )
    admitted = False
    try:
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(process.process, None, ctypes.byref(member)):
            raise ctypes.WinError(ctypes.get_last_error())
        if member.value:
            raise PermissionError(
                errno.EACCES, "Independent process remains in an inherited Windows job."
            )
        if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        admitted = True
        _LOGGER.info("Admitted independent process | child_pid=%s", process.pid)
        return int(process.pid)
    finally:
        try:
            if not admitted:
                native = NativeProcessHandleApi(allow_termination=True)
                native.terminate(process.process)
                if not native.wait(process.process, 5000):
                    raise TimeoutError(
                        "Rejected independent process did not complete native exit."
                    )
                _LOGGER.info(
                    "Retired unadmitted suspended process | child_pid=%s", process.pid
                )
        finally:
            kernel.CloseHandle(process.thread)
            kernel.CloseHandle(process.process)
