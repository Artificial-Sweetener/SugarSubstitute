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

from sugarsubstitute_shared.localization import app_text

from substitute.application.execution import CancellationToken

StatusCallback = Callable[[str], None]
_READY_PATH = "/system_stats"
_REQUEST_TIMEOUT_SECONDS = 0.35
_RETRY_DELAY_SECONDS = 1.0
_TCP_PREFLIGHT_TIMEOUT_SECONDS = 0.005


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
            on_status(app_text("Waiting for ComfyUI to become ready…"))
    return False


def probe_http_ready(*, host: str, port: int) -> bool:
    """Return whether ComfyUI responds successfully to one readiness request."""

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


def is_endpoint_listening(host: str, port: int, *, timeout: float = 0.35) -> bool:
    """Check the HTTP endpoint without acquiring the server's listening address.

    Use a bounded client connection to reject absent endpoints quickly. Binding
    the destination port would race the server that this observer is awaiting.
    """
    try:
        with socket.create_connection(
            (host, port), timeout=min(timeout, _TCP_PREFLIGHT_TIMEOUT_SECONDS)
        ):
            pass
    except OSError:
        return False
    return probe_http_ready(host=host, port=port)


__all__ = ["is_endpoint_listening", "probe_http_ready", "wait_for_ready"]
