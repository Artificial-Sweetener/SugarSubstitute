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
import logging
from pathlib import Path
import subprocess

from sugarsubstitute_shared.windows_process_creation import create_windows_process
from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_job_api import (
    APPLICATION_PROCESS_FAMILY_ENV,
    load_kernel,
)

_LOGGER = logging.getLogger(__name__)
_JOB_OBJECT_QUERY = 0x0004


def start_independent_windows_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
    output_fd: int,
) -> int:
    """Resume a child after Windows accepts explicit native breakaway creation.

    The child must escape the application's immediate kill-on-close family.
    Windows may retain it in a higher-level host job, whose lifetime and policy
    are independent of the application owner. Creation remains suspended until
    membership can be observed and the initial thread can be resumed safely.
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
    child_environment = dict(environment)
    family_name = child_environment.pop(APPLICATION_PROCESS_FAMILY_ENV, None)
    family = 0
    try:
        if family_name:
            family = kernel.OpenJobObjectW(_JOB_OBJECT_QUERY, False, family_name)
            if not family:
                raise ctypes.WinError(ctypes.get_last_error())
        process = create_windows_process(
            command,
            environment=child_environment,
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
            if family:
                retained = wintypes.BOOL()
                if not kernel.IsProcessInJob(
                    process.process, family, ctypes.byref(retained)
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                if retained.value:
                    raise PermissionError(
                        "Independent process remains in the application-owned "
                        "Windows process family."
                    )
            member = wintypes.BOOL()
            if not kernel.IsProcessInJob(process.process, None, ctypes.byref(member)):
                raise ctypes.WinError(ctypes.get_last_error())
            if member.value:
                _LOGGER.info(
                    "Independent process escaped its application-owned family "
                    "but remains governed by a host job | child_pid=%s",
                    process.pid,
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
                        "Retired unadmitted suspended process | child_pid=%s",
                        process.pid,
                    )
            finally:
                kernel.CloseHandle(process.thread)
                kernel.CloseHandle(process.process)
    finally:
        if family:
            kernel.CloseHandle(family)
