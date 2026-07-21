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

"""Probe local endpoint ownership for Substitute-managed ComfyUI processes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ctypes
import os
from pathlib import Path
import socket

from substitute.infrastructure.comfy.managed_process_containment import (
    describe_persisted_containment,
)
from substitute.infrastructure.comfy.managed_readiness import probe_http_ready
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_query import (
    get_listener_pid,
    get_process_command_line,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.managed_process_probe")
_WINDOWS_ERROR_ACCESS_DENIED = 5
_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_SYNCHRONIZE = 0x00100000
_WINDOWS_WAIT_OBJECT_0 = 0x00000000
_WINDOWS_WAIT_TIMEOUT = 0x00000102
_WINDOWS_WAIT_FAILED = 0xFFFFFFFF
_TCP_PREFLIGHT_TIMEOUT_SECONDS = 0.005
_LOOPBACK_BINDABLE_HOSTS = frozenset({"127.0.0.1", "::1"})


class ManagedListenerStatus(str, Enum):
    """Describe the current ownership state of one managed endpoint listener."""

    ABSENT = "absent"
    OWNED_HEALTHY = "owned_healthy"
    OWNED_STALE = "owned_stale"
    FOREIGN = "foreign"


@dataclass(frozen=True)
class ManagedListenerProbeResult:
    """Describe the ownership result for one managed endpoint probe."""

    status: ManagedListenerStatus
    reason: str
    listener_pid: int | None = None
    metadata: ManagedProcessMetadata | None = None


def is_process_running(pid: int | None) -> bool:
    """Return whether the supplied process identifier is still alive."""

    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        return _is_process_running_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _is_process_running_windows(pid: int) -> bool:
    """Return whether one Windows pid is still running."""

    handle = _open_windows_process_handle(pid)
    if handle is None:
        return _get_windows_last_error() == _WINDOWS_ERROR_ACCESS_DENIED
    try:
        wait_result = _wait_for_windows_process_handle(handle)
        if wait_result == _WINDOWS_WAIT_TIMEOUT:
            return True
        if wait_result == _WINDOWS_WAIT_OBJECT_0:
            return False
        log_warning(
            _LOGGER,
            "Unexpected Windows process wait result",
            pid=pid,
            wait_result=wait_result,
        )
        return True
    finally:
        _close_windows_process_handle(handle)


def _open_windows_process_handle(pid: int) -> int | None:
    """Open one Windows process handle for liveness checks."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    access_mask = _WINDOWS_SYNCHRONIZE | _WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION
    handle = int(kernel32.OpenProcess(access_mask, False, pid))
    return handle or None


def _wait_for_windows_process_handle(handle: int) -> int:
    """Return the zero-timeout wait result for one Windows process handle."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return int(kernel32.WaitForSingleObject(handle, 0))


def _close_windows_process_handle(handle: int) -> None:
    """Close one Windows process handle acquired for liveness checks."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(handle)


def _get_windows_last_error() -> int:
    """Return the current Windows thread-local last-error value."""

    return int(ctypes.get_last_error())


def is_endpoint_listening(host: str, port: int, *, timeout: float = 0.35) -> bool:
    """Return whether the supplied host and port serve the ComfyUI HTTP API."""

    if _can_probe_local_port_availability(host) and _local_port_is_available(
        host=host,
        port=port,
    ):
        return False
    if not _tcp_endpoint_accepts_connections(
        host=host,
        port=port,
        timeout=min(timeout, _TCP_PREFLIGHT_TIMEOUT_SECONDS),
    ):
        return False
    return probe_http_ready(host=host, port=port)


def _can_probe_local_port_availability(host: str) -> bool:
    """Return whether bind availability is authoritative for one literal host."""

    return host in _LOOPBACK_BINDABLE_HOSTS


def _local_port_is_available(*, host: str, port: int) -> bool:
    """Return whether one literal loopback port can be bound immediately."""

    family = socket.AF_INET6 if host == "::1" else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        return False
    return True


def _tcp_endpoint_accepts_connections(
    *,
    host: str,
    port: int,
    timeout: float,
) -> bool:
    """Return whether one TCP endpoint accepts a short connection preflight."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_managed_listener(
    *,
    host: str,
    port: int,
    workspace: Path,
    metadata: ManagedProcessMetadata | None,
) -> ManagedListenerProbeResult:
    """Classify the current listener as healthy-owned, stale-owned, foreign, or absent."""

    metadata_matches = metadata is not None and metadata.matches_endpoint(
        host=host,
        port=port,
        workspace=workspace,
    )
    endpoint_listening = is_endpoint_listening(host, port)
    listener_pid = get_listener_pid(host, port) if endpoint_listening else None

    if endpoint_listening:
        if (
            metadata_matches
            and metadata is not None
            and _is_owned_listener_alive(metadata, listener_pid)
        ):
            return ManagedListenerProbeResult(
                status=ManagedListenerStatus.OWNED_HEALTHY,
                reason="Managed listener is already healthy and owned by Substitute.",
                listener_pid=listener_pid,
                metadata=metadata,
            )
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.FOREIGN,
            reason=(
                "Another process is already listening on the managed ComfyUI address."
            ),
            listener_pid=listener_pid,
            metadata=metadata,
        )

    if (
        metadata_matches
        and metadata is not None
        and _is_owned_process_identity_alive(metadata)
    ):
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.OWNED_STALE,
            reason=(
                "Substitute found a stale owned managed ComfyUI process that is no "
                "longer serving the configured address."
            ),
            metadata=metadata,
        )
    if metadata_matches:
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason=(
                "Substitute found stale managed ownership metadata with no active "
                "listener or live owned process."
            ),
            metadata=metadata,
        )
    return ManagedListenerProbeResult(
        status=ManagedListenerStatus.ABSENT,
        reason="No managed ComfyUI listener is running on the configured address.",
    )


def _is_owned_listener_alive(
    metadata: ManagedProcessMetadata,
    listener_pid: int | None,
) -> bool:
    """Return whether the resolved listener still belongs to the owned metadata record."""

    if not _is_owned_process_identity_alive(metadata):
        return False
    if listener_pid is None:
        log_warning(
            _LOGGER,
            "Managed listener pid could not be resolved; falling back to metadata pid",
            pid=metadata.pid,
            host=metadata.host,
            port=metadata.port,
        )
        return True
    return listener_pid == metadata.pid


def _is_owned_process_identity_alive(metadata: ManagedProcessMetadata) -> bool:
    """Return whether the saved pid still belongs to the expected managed process."""

    containment_status = describe_persisted_containment(metadata)
    if containment_status.managed_process_running:
        command_line = get_process_command_line(metadata.pid)
        if command_line is None:
            return False
        return _command_line_matches_metadata(
            command_line=command_line, metadata=metadata
        )
    if metadata.containment_mode == "posix_guardian":
        return (
            containment_status.owner_process_running
            or containment_status.process_group_running
        )
    if not containment_status.managed_process_running:
        return False
    return False


def _command_line_matches_metadata(
    *,
    command_line: str,
    metadata: ManagedProcessMetadata,
) -> bool:
    """Return whether one process command line still matches the saved managed launch."""

    normalized_command = command_line.casefold()
    normalized_main = str((metadata.workspace_path / "main.py").resolve()).casefold()
    return (
        normalized_main in normalized_command
        and f"--listen {metadata.host}".casefold() in normalized_command
        and f"--port {metadata.port}".casefold() in normalized_command
    )


__all__ = [
    "ManagedListenerProbeResult",
    "ManagedListenerStatus",
    "is_endpoint_listening",
    "is_process_running",
    "probe_managed_listener",
]
