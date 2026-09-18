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

"""Create native children with explicit inherited handles and optional job admission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess

from sugarsubstitute_shared.windows_process_job_api import (
    ProcessInformation,
    StartupInfoEx,
    load_kernel,
)


def create_windows_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path | None,
    output_fd: int,
    creation_flags: int,
    error_fd: int | None = None,
    job: int | None = None,
) -> ProcessInformation:
    """Transfer process/thread handles only after atomic native creation succeeds.

    The caller owns both returned handles and the child's admission policy.
    Only the explicit standard handles are inherited; an optional job is assigned
    at creation so no instruction can run outside its required containment.
    """
    import msvcrt

    if not command or any("\0" in argument for argument in command):
        raise ValueError("A process command must contain valid arguments.")
    if any(
        not key or "=" in key or "\0" in key or "\0" in value
        for key, value in environment.items()
    ):
        raise ValueError("A process environment must contain valid names and values.")
    kernel = load_kernel()
    handles: list[int] = []
    attributes_initialized = False
    size = ctypes.c_size_t()
    attribute_count = 1 if job is None else 2
    kernel.InitializeProcThreadAttributeList(
        None, attribute_count, 0, ctypes.byref(size)
    )
    if not size.value:
        raise ctypes.WinError(ctypes.get_last_error())
    attributes = ctypes.create_string_buffer(size.value)
    try:
        if not kernel.InitializeProcThreadAttributeList(
            attributes, attribute_count, 0, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        attributes_initialized = True
        with open(os.devnull, "rb") as null_input:
            for fd in (
                null_input.fileno(),
                output_fd,
                output_fd if error_fd is None else error_fd,
            ):
                duplicate = wintypes.HANDLE()
                current = kernel.GetCurrentProcess()
                if not kernel.DuplicateHandle(
                    current,
                    msvcrt.get_osfhandle(fd),
                    current,
                    ctypes.byref(duplicate),
                    0,
                    True,
                    2,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                assert duplicate.value is not None
                handles.append(duplicate.value)
            inherited = (wintypes.HANDLE * len(handles))(*handles)
            if not kernel.UpdateProcThreadAttribute(
                attributes,
                0,
                0x00020002,
                ctypes.byref(inherited),
                ctypes.sizeof(inherited),
                None,
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if job is not None:
                jobs = (wintypes.HANDLE * 1)(job)
                if not kernel.UpdateProcThreadAttribute(
                    attributes,
                    0,
                    0x0002000D,
                    ctypes.byref(jobs),
                    ctypes.sizeof(jobs),
                    None,
                    None,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
            startup = StartupInfoEx()
            startup.startup.size = ctypes.sizeof(startup)
            startup.startup.flags = 0x00000100
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = (
                handles
            )
            startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
            block = ctypes.create_unicode_buffer(
                "\0".join(
                    f"{key}={value}"
                    for key, value in sorted(
                        environment.items(), key=lambda item: item[0].upper()
                    )
                )
                + "\0"
            )
            process = ProcessInformation()
            if not kernel.CreateProcessW(
                command[0],
                ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
                None,
                None,
                True,
                creation_flags | 0x00080000 | 0x00000400,
                block,
                str(cwd) if cwd is not None else None,
                ctypes.byref(startup),
                ctypes.byref(process),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        return process
    finally:
        if attributes_initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        for handle in handles:
            kernel.CloseHandle(handle)
