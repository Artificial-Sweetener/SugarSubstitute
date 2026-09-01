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

"""Cover Comfy connection monitor lifecycle and edge reporting."""

from __future__ import annotations

from typing import Any

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.connection_monitor import ComfyConnectionMonitor


class _Cancellation:
    """Provide mutable cancellation state for synchronous monitor tests."""

    def __init__(self) -> None:
        """Initialize an active cancellation source."""

        self.is_cancelled = False


class _TaskHandle:
    """Provide the task-handle surface used by monitor lifecycle tests."""

    def __init__(self) -> None:
        """Initialize an unfinished handle."""

        self.is_finished = False
        self.stop_reasons: list[str] = []

    def stop(self, *, reason: str) -> None:
        """Record shutdown and complete the fake task."""

        self.stop_reasons.append(reason)
        self.is_finished = True


class _DisconnectingWebSocket:
    """Connect once and then emulate a closed Comfy websocket."""

    def __init__(self) -> None:
        """Initialize transport call tracking."""

        self.connect_urls: list[str] = []
        self.timeout: float | None = None
        self.closed = False

    def connect(self, url: str, *, timeout: float) -> None:
        """Record the monitor websocket connection."""

        self.connect_urls.append(url)
        self.timeout = timeout

    def settimeout(self, timeout: float) -> None:
        """Record the receive timeout."""

        self.timeout = timeout

    def recv(self) -> str:
        """Return an empty payload to represent a closed channel."""

        return ""

    def close(self) -> None:
        """Record transport cleanup."""

        self.closed = True


class _FailingWebSocket:
    """Fail before a monitor channel can establish."""

    def connect(self, _url: str, *, timeout: float) -> None:
        """Raise an initial connection failure after accepting the timeout."""

        del timeout
        raise ConnectionError("Comfy is unavailable")

    def close(self) -> None:
        """Provide transport cleanup after failed connection."""


def test_monitor_reports_connection_and_disconnection_edges() -> None:
    """One opened and closed channel should emit one callback for each edge."""

    cancellation = _Cancellation()
    websocket_client = _DisconnectingWebSocket()
    events: list[str] = []
    captured_work: list[Any] = []
    handle = _TaskHandle()

    def on_disconnected() -> None:
        """Record disconnection and stop the synchronous monitor loop."""

        events.append("disconnected")
        cancellation.is_cancelled = True

    def task_factory(
        _identity: object,
        _context: object,
        work: Any,
        _thread_name: str,
    ) -> _TaskHandle:
        """Capture monitor work without starting a real thread."""

        captured_work.append(work)
        return handle

    monitor = ComfyConnectionMonitor(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        on_connected=lambda: events.append("connected"),
        on_disconnected=on_disconnected,
        websocket_factory=lambda: websocket_client,
        task_factory=task_factory,
        backoff_seconds=(0.0,),
    )

    monitor.start()
    captured_work[0](cancellation)

    assert events == ["connected", "disconnected"]
    assert websocket_client.connect_urls[0].startswith(
        "ws://127.0.0.1:8188/ws?clientId=substitute-health-"
    )
    assert websocket_client.timeout == 5.0
    assert websocket_client.closed is True


def test_monitor_start_and_stop_are_idempotent() -> None:
    """Repeated lifecycle requests should retain one task and one stop request."""

    handle = _TaskHandle()
    task_requests: list[object] = []

    def task_factory(
        _identity: object,
        _context: object,
        work: Any,
        _thread_name: str,
    ) -> _TaskHandle:
        """Record task creation without running monitor work."""

        task_requests.append(work)
        return handle

    monitor = ComfyConnectionMonitor(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        on_connected=lambda: None,
        on_disconnected=lambda: None,
        task_factory=task_factory,
    )

    monitor.start()
    monitor.start()
    monitor.stop()
    monitor.stop()

    assert len(task_requests) == 1
    assert handle.stop_reasons == ["comfy_connection_monitor_stop"]


def test_monitor_reports_initial_connection_failure_as_an_outage() -> None:
    """Failure before first connection should still gate the ready shell."""

    cancellation = _Cancellation()
    captured_work: list[Any] = []
    events: list[str] = []

    def on_disconnected() -> None:
        """Record the initial outage and stop the synchronous retry loop."""

        events.append("disconnected")
        cancellation.is_cancelled = True

    def task_factory(
        _identity: object,
        _context: object,
        work: Any,
        _thread_name: str,
    ) -> _TaskHandle:
        """Capture monitor work without starting a real thread."""

        captured_work.append(work)
        return _TaskHandle()

    monitor = ComfyConnectionMonitor(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        on_connected=lambda: events.append("connected"),
        on_disconnected=on_disconnected,
        websocket_factory=_FailingWebSocket,
        task_factory=task_factory,
        backoff_seconds=(0.0,),
    )

    monitor.start()
    captured_work[0](cancellation)

    assert events == ["disconnected"]
