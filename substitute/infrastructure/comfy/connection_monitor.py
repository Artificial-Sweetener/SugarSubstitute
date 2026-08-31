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

"""Monitor the active Comfy websocket independently of generation work."""

from __future__ import annotations

import time
from collections.abc import Callable
from itertools import count
from typing import Any, Protocol, cast
from uuid import uuid4

import websocket

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_DEFAULT_BACKOFF_SECONDS = (0.3, 1.0, 2.0, 5.0)
_MONITOR_REQUEST_IDS = count(1)
_LOGGER = get_logger("infrastructure.comfy.connection_monitor")

ConnectionCallback = Callable[[], None]
WebSocketFactory = Callable[[], Any]
MonitorTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, LongLivedWork[None], str],
    "MonitorTaskHandle",
]


class MonitorTaskHandle(Protocol):
    """Describe the long-lived task handle used by the connection monitor."""

    @property
    def is_finished(self) -> bool:
        """Return whether the monitor task has completed."""

    def stop(self, *, reason: str) -> None:
        """Request monitor task shutdown."""


class ComfyConnectionMonitor:
    """Maintain a persistent websocket and report connection edge transitions."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        on_connected: ConnectionCallback,
        on_disconnected: ConnectionCallback,
        websocket_factory: WebSocketFactory | None = None,
        task_factory: MonitorTaskFactory | None = None,
        backoff_seconds: tuple[float, ...] = _DEFAULT_BACKOFF_SECONDS,
        receive_timeout_seconds: float = 5.0,
    ) -> None:
        """Store transport and task dependencies for persistent monitoring."""

        if not backoff_seconds:
            raise ValueError("backoff_seconds must not be empty")
        self._endpoint = endpoint
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._websocket_factory = websocket_factory or websocket.WebSocket
        self._task_factory = task_factory
        self._backoff_seconds = backoff_seconds
        self._receive_timeout_seconds = receive_timeout_seconds
        self._handle: MonitorTaskHandle | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the monitor task is currently active."""

        handle = self._handle
        return handle is not None and not handle.is_finished

    def start(self) -> None:
        """Start persistent connection monitoring once."""

        if self.is_running:
            return
        if self._task_factory is None:
            log_warning(
                _LOGGER,
                "Comfy connection monitor has no execution task factory",
                host=self._endpoint.host,
                port=self._endpoint.port,
            )
            return
        self._handle = self._task_factory(
            TaskIdentity(
                request_id=next(_MONITOR_REQUEST_IDS),
                domain="comfy_connection_monitor",
            ),
            ExecutionContext(
                operation="comfy_connection_monitor",
                reason="connection_health",
                lane="backend_event_listener",
                safe_fields=(
                    ("host", self._endpoint.host),
                    ("port", self._endpoint.port),
                ),
            ),
            self._run,
            "substitute-comfy-connection-monitor",
        )

    def stop(self) -> None:
        """Request monitor shutdown through its long-lived task owner."""

        handle = self._handle
        if handle is None:
            return
        handle.stop(reason="comfy_connection_monitor_stop")
        if handle.is_finished:
            self._handle = None

    def _run(self, cancellation: CancellationSource) -> None:
        """Reconnect until stopped while reporting each connection edge once."""

        backoff_index = 0
        connected = False
        disconnected_reported = False

        def report_connected() -> None:
            """Record and publish a newly opened monitor channel."""

            nonlocal connected, disconnected_reported
            if connected:
                return
            connected = True
            disconnected_reported = False
            self._on_connected()

        def report_disconnected() -> None:
            """Publish initial or established connection loss once per outage."""

            nonlocal connected, disconnected_reported
            if disconnected_reported:
                return
            connected = False
            disconnected_reported = True
            self._on_disconnected()

        while not cancellation.is_cancelled:
            try:
                self._listen_once(cancellation, report_connected)
                backoff_index = 0
            except Exception as exc:
                if cancellation.is_cancelled:
                    return
                report_disconnected()
                delay = self._backoff_seconds[
                    min(backoff_index, len(self._backoff_seconds) - 1)
                ]
                backoff_index += 1
                if _is_expected_disconnect(exc):
                    log_warning(
                        _LOGGER,
                        "Comfy connection monitor disconnected; reconnecting",
                        reconnect_delay_seconds=delay,
                        error_type=type(exc).__name__,
                        host=self._endpoint.host,
                        port=self._endpoint.port,
                    )
                else:
                    log_exception(
                        _LOGGER,
                        "Comfy connection monitor failed; reconnecting",
                        reconnect_delay_seconds=delay,
                        host=self._endpoint.host,
                        port=self._endpoint.port,
                    )
                self._sleep_until_cancelled(cancellation, delay)
                continue
            if cancellation.is_cancelled:
                return
            report_disconnected()

            # A normal receive-loop return also represents a closed channel.
            self._sleep_until_cancelled(cancellation, self._backoff_seconds[0])

    def _listen_once(
        self,
        cancellation: CancellationSource,
        report_connected: ConnectionCallback,
    ) -> None:
        """Open one websocket and block until cancellation or disconnection."""

        client = self._websocket_factory()
        client_id = f"substitute-health-{uuid4().hex}"
        url = self._endpoint.websocket_url(client_id)
        try:
            try:
                cast(Any, client).connect(url, timeout=self._receive_timeout_seconds)
            except TypeError:
                cast(Any, client).connect(url)
            settimeout = getattr(client, "settimeout", None)
            if callable(settimeout):
                settimeout(self._receive_timeout_seconds)
            log_info(
                _LOGGER,
                "Comfy connection monitor connected",
                host=self._endpoint.host,
                port=self._endpoint.port,
                client_id=client_id,
            )
            report_connected()
            while not cancellation.is_cancelled:
                try:
                    payload = client.recv()
                except Exception as exc:
                    if _is_timeout_error(exc):
                        continue
                    raise
                if payload in {None, ""}:
                    raise ConnectionError("Comfy websocket closed")
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    log_warning(
                        _LOGGER,
                        "Failed to close Comfy connection monitor websocket",
                        host=self._endpoint.host,
                        port=self._endpoint.port,
                    )

    @staticmethod
    def _sleep_until_cancelled(
        cancellation: CancellationSource,
        delay_seconds: float,
    ) -> None:
        """Sleep in short intervals so task cancellation remains responsive."""

        deadline = time.monotonic() + delay_seconds
        while not cancellation.is_cancelled and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _is_timeout_error(exc: Exception) -> bool:
    """Return whether an exception represents receive-timeout semantics."""

    text = str(exc).lower()
    return "timed out" in text or "timeout" in text


def _is_expected_disconnect(exc: Exception) -> bool:
    """Return whether an exception is expected during connection loss."""

    return isinstance(
        exc,
        (
            websocket.WebSocketConnectionClosedException,
            websocket.WebSocketException,
            ConnectionError,
            OSError,
        ),
    )


__all__ = ["ComfyConnectionMonitor"]
