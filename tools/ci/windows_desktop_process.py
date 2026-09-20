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

"""Launch Windows qualification targets across the hosted process-job boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
import subprocess

from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_job_api import load_kernel

_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_WMI_SUCCESS = 0


@dataclass(slots=True)
class WindowsDesktopProcess:
    """Retain a WMI-created process object for reliable status polling."""

    pid: int
    _handle: int
    _native: NativeProcessHandleApi = field(default_factory=NativeProcessHandleApi)
    _returncode: int | None = None

    def poll(self) -> int | None:
        """Return the exit code once and release the retained process handle."""

        if self._returncode is not None:
            return self._returncode
        if not self._native.wait(self._handle, 0):
            return None
        self._returncode = self._native.exit_code(self._handle)
        self._native.close(self._handle)
        self._handle = 0
        return self._returncode

    def wait(self, timeout_seconds: float) -> int:
        """Wait a bounded interval for completion and return the native exit code."""

        if self._returncode is not None:
            return self._returncode
        if not self._native.wait(self._handle, round(timeout_seconds * 1_000)):
            raise TimeoutError(
                f"Windows desktop process {self.pid} did not exit within "
                f"{timeout_seconds} seconds."
            )
        return_code = self.poll()
        assert return_code is not None
        return return_code


def start_windows_desktop_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
) -> WindowsDesktopProcess:
    """Start a local interactive process outside the qualification host job.

    Windows Management Instrumentation owns the local process-creation boundary,
    and its startup contract explicitly requests job breakaway. This reproduces
    an ordinary desktop launch instead of nesting an immutable released updater
    inside the CI runner or agent's kill-on-close job.
    """

    import win32com.client  # type: ignore[import-untyped]

    wmi = win32com.client.GetObject(
        "winmgmts:{impersonationLevel=impersonate}!root\\cimv2"
    )
    process_class = wmi.Get("Win32_Process")
    startup = wmi.Get("Win32_ProcessStartup").SpawnInstance_()
    startup.CreateFlags = _CREATE_BREAKAWAY_FROM_JOB | _CREATE_UNICODE_ENVIRONMENT
    startup.EnvironmentVariables = tuple(
        f"{key}={value}"
        for key, value in sorted(environment.items(), key=lambda item: item[0].upper())
    )
    startup.ShowWindow = 1
    startup.WinstationDesktop = "winsta0\\default"
    parameters = process_class.Methods_("Create").InParameters.SpawnInstance_()
    parameters.CommandLine = subprocess.list2cmdline(command)
    parameters.CurrentDirectory = str(cwd)
    parameters.ProcessStartupInformation = startup
    result = wmi.ExecMethod("Win32_Process", "Create", parameters)
    return_value = int(result.ReturnValue)
    if return_value != _WMI_SUCCESS:
        raise OSError(
            return_value,
            "Windows desktop process creation failed through local WMI.",
        )
    process_id = int(result.ProcessId)
    native = NativeProcessHandleApi(allow_termination=True)
    handle = native.open(process_id)
    if handle is None:
        raise ProcessLookupError(
            process_id,
            "Windows desktop process exited before qualification retained it.",
        )
    member = wintypes.BOOL()
    kernel = load_kernel()
    if not kernel.IsProcessInJob(handle, None, ctypes.byref(member)):
        native.close(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    if member.value:
        native.terminate(handle)
        native.wait(handle, 5_000)
        native.close(handle)
        raise RuntimeError(
            "Windows desktop qualification target remained inside a job object."
        )
    return WindowsDesktopProcess(
        pid=process_id,
        _handle=handle,
        _native=native,
    )


__all__ = ["WindowsDesktopProcess", "start_windows_desktop_process"]
