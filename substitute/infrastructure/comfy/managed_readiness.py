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

"""Provide managed-local Comfy readiness polling helpers."""

from __future__ import annotations

from collections.abc import Callable
import http.client
import socket
import time

from substitute.application.execution import CancellationToken

StatusCallback = Callable[[str], None]
_READY_PATH = "/system_stats"
_REQUEST_TIMEOUT_SECONDS = 0.35
_RETRY_DELAY_SECONDS = 1.0
_LOOPBACK_BINDABLE_HOSTS = frozenset({"127.0.0.1", "::1"})


def wait_for_ready(
    host: str,
    port: int,
    *,
    timeout: float = 300.0,
    on_status: StatusCallback | None = None,
    cancellation: CancellationToken | None = None,
) -> bool:
    """Poll ComfyUI's HTTP API until it responds or startup is canceled."""

    started_at = time.monotonic()
    while time.monotonic() - started_at < timeout:
        if cancellation is not None and cancellation.is_cancelled:
            return False
        if probe_http_ready(host=host, port=port):
            return True
        time.sleep(_RETRY_DELAY_SECONDS)
        if on_status is not None:
            on_status("Waiting for ComfyUI to become ready…")
    return False


def probe_http_ready(*, host: str, port: int) -> bool:
    """Return whether ComfyUI responds successfully to one readiness request."""

    if _can_probe_local_port_availability(host) and _local_port_is_available(
        host=host,
        port=port,
    ):
        return False

    connection = http.client.HTTPConnection(
        host,
        port,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    try:
        connection.request("GET", _READY_PATH, headers={"Connection": "close"})
        response = connection.getresponse()
        response.read()
        return response.status == http.client.OK
    except OSError:
        return False
    finally:
        connection.close()


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


__all__ = ["probe_http_ready", "wait_for_ready"]
