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

"""Own managed ComfyUI lifetime on Windows through kill-on-close Job Objects."""

from __future__ import annotations

from collections.abc import Mapping
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
from typing import IO
from uuid import uuid4

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentError,
    ManagedContainmentLaunchRequest,
    ManagedContainmentLaunchResult,
    ManagedContainmentRuntimeStatus,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import is_process_running
from substitute.shared.logging.logger import get_logger, log_info
from sugarsubstitute_shared.windows_long_paths import (
    ExternalLongPathCompatibilityError,
    external_long_path_error,
    subprocess_working_directory,
)

_LOGGER = get_logger("infrastructure.comfy.windows_job_containment")
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_HANDLE_FLAG_INHERIT = 0x00000001
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_STARTF_USESTDHANDLES = 0x00000100
_STD_INPUT_HANDLE = -10
_STILL_ACTIVE = 259
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    """Represent Windows SECURITY_ATTRIBUTES for inheritable handle creation."""

    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _STARTUPINFOW(ctypes.Structure):
    """Represent STARTUPINFOW for CreateProcessW."""

    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    """Represent PROCESS_INFORMATION returned by CreateProcessW."""

    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    """Represent the Win32 IO_COUNTERS payload for job configuration."""

    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    """Represent the basic limit configuration for one Job Object."""

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    """Represent extended job limits including kill-on-close configuration."""

    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@dataclass(frozen=True)
class _CreatedProcess:
    """Capture the raw handles returned by the suspended launch step."""

    pid: int
    process_handle: int
    thread_handle: int


class WindowsManagedProcess:
    """Expose one Windows managed child through the lifecycle process protocol."""

    def __init__(
        self,
        *,
        pid: int,
        process_handle: int,
        stdout_stream: IO[bytes] | None,
    ) -> None:
        """Store the raw process handle and optional stdout stream."""

        self.pid = pid
        self.stdout = stdout_stream
        self._process_handle = process_handle

    def poll(self) -> int | None:
        """Return the child exit code when the process has exited."""

        wait_result = _wait_for_handle(self._process_handle, timeout_ms=0)
        if wait_result == _WAIT_TIMEOUT:
            return None
        if wait_result != _WAIT_OBJECT_0:
            return 1
        return _get_process_exit_code(self._process_handle)


@dataclass
class WindowsJobContainmentHandle:
    """Retain the owning Job Object and process handles for app lifetime."""

    job_handle: int
    process_handle: int
    job_name: str
    _closed: bool = False

    def close(self) -> None:
        """Close the owned job and process handles exactly once."""

        if self._closed:
            return
        self._closed = True
        _close_handle(self.job_handle)
        _close_handle(self.process_handle)


def launch_in_job(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    request: ManagedContainmentLaunchRequest,
) -> ManagedContainmentLaunchResult:
    """Launch one managed ComfyUI process inside a kill-on-close Job Object."""

    job_name = f"substitute-comfy-{os.getpid()}-{uuid4().hex[:12]}"
    job_handle = 0
    thread_handle = 0
    stdout_write_handle = 0
    stdout_stream: IO[bytes] | None = None
    created_process: _CreatedProcess | None = None
    try:
        log_info(
            _LOGGER,
            "Contained launch requested",
            containment_mode="windows_job_object",
            launch_phase="requested",
            workspace=str(workspace),
        )
        job_handle = _create_job_object(job_name)
        _configure_kill_on_job_close(job_handle)
        if request.capture_output:
            stdout_stream, stdout_write_handle = _create_stdout_pipe()
        created_process = _create_suspended_process(
            request=request,
            stdout_write_handle=stdout_write_handle or None,
        )
        thread_handle = created_process.thread_handle
        _assign_process_to_job(
            job_handle=job_handle, process_handle=created_process.process_handle
        )
        _resume_primary_thread(thread_handle)
        _close_handle(thread_handle)
        thread_handle = 0
        if stdout_write_handle:
            _close_handle(stdout_write_handle)
            stdout_write_handle = 0
        process = WindowsManagedProcess(
            pid=created_process.pid,
            process_handle=created_process.process_handle,
            stdout_stream=stdout_stream,
        )
        containment_handle = WindowsJobContainmentHandle(
            job_handle=job_handle,
            process_handle=created_process.process_handle,
            job_name=job_name,
        )
        metadata = ManagedProcessMetadata(
            pid=created_process.pid,
            host=endpoint.host,
            port=endpoint.port,
            workspace_path=workspace,
            parent_pid=os.getpid(),
            last_launched_at=_timestamp_now(),
            containment_mode="windows_job_object",
            owner_pid=os.getpid(),
            job_name=job_name,
        )
        log_info(
            _LOGGER,
            "Windows process assigned to job",
            containment_mode="windows_job_object",
            launch_phase="assigned",
            owner_pid=metadata.owner_pid,
            managed_pid=metadata.pid,
            job_name=job_name,
        )
        return ManagedContainmentLaunchResult(
            process=process,
            metadata=metadata,
            stdout_stream=stdout_stream,
            containment_handle=containment_handle,
        )
    except Exception as error:
        if stdout_write_handle:
            _close_handle(stdout_write_handle)
        if thread_handle:
            _close_handle(thread_handle)
        if created_process is not None:
            _close_handle(created_process.process_handle)
        if job_handle:
            _close_handle(job_handle)
        if stdout_stream is not None:
            stdout_stream.close()
        if isinstance(error, ExternalLongPathCompatibilityError):
            raise
        compatibility_error = external_long_path_error(
            component="ComfyUI",
            path=workspace,
            detail=error,
        )
        if compatibility_error is not None:
            raise compatibility_error from error
        raise ManagedContainmentError(
            f"Windows Job Object containment failed: {error}"
        ) from error


def close_job_containment_handle(handle: WindowsJobContainmentHandle) -> None:
    """Close the owning Job Object handle to trigger kill-on-close cleanup."""

    handle.close()


def describe_windows_job_runtime(
    metadata: ManagedProcessMetadata,
) -> ManagedContainmentRuntimeStatus:
    """Return persisted runtime facts for one Windows job-owned launch."""

    return ManagedContainmentRuntimeStatus(
        managed_process_running=is_process_running(metadata.pid),
        owner_process_running=is_process_running(metadata.owner_pid),
        process_group_running=False,
    )


def _create_job_object(job_name: str) -> int:
    """Create one named Windows Job Object for managed Comfy containment."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    job_handle = int(kernel32.CreateJobObjectW(None, job_name))
    if not job_handle:
        raise _last_windows_error("CreateJobObjectW")
    log_info(
        _LOGGER,
        "Windows job created",
        containment_mode="windows_job_object",
        launch_phase="job_created",
        job_name=job_name,
    )
    return job_handle


def _configure_kill_on_job_close(job_handle: int) -> None:
    """Enable kill-on-close semantics for one managed Job Object."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    limit_info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limit_info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    success = kernel32.SetInformationJobObject(
        wintypes.HANDLE(job_handle),
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(limit_info),
        ctypes.sizeof(limit_info),
    )
    if not success:
        raise _last_windows_error("SetInformationJobObject")


def _create_stdout_pipe() -> tuple[IO[bytes], int]:
    """Create one inheritable stdout pipe and return the parent read stream."""

    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    security_attributes = _SECURITY_ATTRIBUTES()
    security_attributes.nLength = ctypes.sizeof(_SECURITY_ATTRIBUTES)
    security_attributes.bInheritHandle = True
    read_handle = wintypes.HANDLE()
    write_handle = wintypes.HANDLE()
    success = kernel32.CreatePipe(
        ctypes.byref(read_handle),
        ctypes.byref(write_handle),
        ctypes.byref(security_attributes),
        0,
    )
    if not success:
        raise _last_windows_error("CreatePipe")
    if not kernel32.SetHandleInformation(
        read_handle,
        _HANDLE_FLAG_INHERIT,
        0,
    ):
        read_raw_handle = read_handle.value
        write_raw_handle = write_handle.value
        if read_raw_handle is not None:
            _close_handle(int(read_raw_handle))
        if write_raw_handle is not None:
            _close_handle(int(write_raw_handle))
        raise _last_windows_error("SetHandleInformation")
    read_raw_handle = read_handle.value
    write_raw_handle = write_handle.value
    assert read_raw_handle is not None
    assert write_raw_handle is not None
    read_fd = msvcrt.open_osfhandle(int(read_raw_handle), os.O_RDONLY)
    stdout_stream = os.fdopen(read_fd, "rb", buffering=0)
    return stdout_stream, int(write_raw_handle)


def _create_suspended_process(
    *,
    request: ManagedContainmentLaunchRequest,
    stdout_write_handle: int | None,
) -> _CreatedProcess:
    """Create one suspended managed process before Job Object assignment."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    startup_info = _STARTUPINFOW()
    startup_info.cb = ctypes.sizeof(_STARTUPINFOW)
    inherit_handles = False
    if stdout_write_handle is not None:
        startup_info.dwFlags |= _STARTF_USESTDHANDLES
        startup_info.hStdOutput = wintypes.HANDLE(stdout_write_handle)
        startup_info.hStdError = wintypes.HANDLE(stdout_write_handle)
        startup_info.hStdInput = wintypes.HANDLE(
            kernel32.GetStdHandle(_STD_INPUT_HANDLE)
        )
        inherit_handles = True
    process_info = _PROCESS_INFORMATION()
    command_line = ctypes.create_unicode_buffer(
        subprocess.list2cmdline(list(request.command))
    )
    environment_block = _build_environment_block(request.env)
    creation_flags = (
        _CREATE_SUSPENDED | _CREATE_NEW_PROCESS_GROUP | _CREATE_UNICODE_ENVIRONMENT
    )
    success = kernel32.CreateProcessW(
        None,
        command_line,
        None,
        None,
        inherit_handles,
        creation_flags,
        environment_block,
        subprocess_working_directory(request.cwd),
        ctypes.byref(startup_info),
        ctypes.byref(process_info),
    )
    if not success:
        raise _last_windows_error("CreateProcessW")
    return _CreatedProcess(
        pid=int(process_info.dwProcessId),
        process_handle=int(process_info.hProcess),
        thread_handle=int(process_info.hThread),
    )


def _assign_process_to_job(*, job_handle: int, process_handle: int) -> None:
    """Assign one suspended child process to the owning Job Object."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    success = kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(job_handle),
        wintypes.HANDLE(process_handle),
    )
    if not success:
        raise _last_windows_error("AssignProcessToJobObject")


def _resume_primary_thread(thread_handle: int) -> None:
    """Resume one previously suspended Windows primary thread."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    previous_suspend_count = int(kernel32.ResumeThread(wintypes.HANDLE(thread_handle)))
    if previous_suspend_count == -1:
        raise _last_windows_error("ResumeThread")


def _build_environment_block(
    environment: Mapping[str, str],
) -> ctypes.Array[ctypes.c_wchar]:
    """Render one CreateProcessW environment block with a double-null terminator."""

    serialized_entries = [f"{key}={value}" for key, value in environment.items()]
    serialized_entries.sort(key=str.casefold)
    return ctypes.create_unicode_buffer("\0".join(serialized_entries) + "\0\0")


def _wait_for_handle(handle: int, *, timeout_ms: int) -> int:
    """Return the zero-timeout wait result for one Windows handle."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return int(kernel32.WaitForSingleObject(wintypes.HANDLE(handle), timeout_ms))


def _get_process_exit_code(process_handle: int) -> int:
    """Return the current Windows process exit code."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    exit_code = wintypes.DWORD()
    success = kernel32.GetExitCodeProcess(
        wintypes.HANDLE(process_handle),
        ctypes.byref(exit_code),
    )
    if not success:
        raise _last_windows_error("GetExitCodeProcess")
    return 0 if exit_code.value == _STILL_ACTIVE else int(exit_code.value)


def _close_handle(handle: int) -> None:
    """Close one raw Windows handle when it is non-zero."""

    if handle:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle(wintypes.HANDLE(handle))


def _last_windows_error(operation: str) -> OSError:
    """Return one formatted Win32 failure with the current last-error value."""

    return OSError(f"{operation} failed: {ctypes.WinError(ctypes.get_last_error())}")


def _timestamp_now() -> str:
    """Return one UTC timestamp for managed launch metadata."""

    return datetime.now(UTC).isoformat()


__all__ = [
    "WindowsJobContainmentHandle",
    "WindowsManagedProcess",
    "close_job_containment_handle",
    "describe_windows_job_runtime",
    "launch_in_job",
]
