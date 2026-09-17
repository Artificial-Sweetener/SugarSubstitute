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

"""Tests for managed ComfyUI HTTP readiness polling."""

from __future__ import annotations

from types import SimpleNamespace
from collections.abc import Iterator
from contextlib import contextmanager
import socket

import pytest

from substitute.application.execution import CancellationSource
from substitute.infrastructure.comfy import managed_readiness


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
@pytest.mark.parametrize("status", [200, 503])
def test_probe_http_ready_uses_system_stats_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    status: int,
) -> None:
    """Readiness probe should use ComfyUI's HTTP API instead of a raw socket."""

    observed: dict[str, object] = {}

    class _FakeConnection:
        """Capture one readiness request and return an HTTP 200 response."""

        def __init__(self, host: str, port: int, timeout: float) -> None:
            observed["host"] = host
            observed["port"] = port
            observed["timeout"] = timeout

        def request(
            self,
            method: str,
            path: str,
            body: object | None = None,
            headers: dict[str, str] | None = None,
        ) -> None:
            _ = body
            observed["method"] = method
            observed["path"] = path
            observed["headers"] = headers

        def getresponse(self) -> SimpleNamespace:
            return SimpleNamespace(status=status, read=lambda: b"{}")

        def close(self) -> None:
            observed["closed"] = True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.http.client.HTTPConnection",
        _FakeConnection,
    )

    assert managed_readiness.probe_http_ready(host=host, port=8188) is (status == 200)
    assert observed == {
        "host": host,
        "port": 8188,
        "timeout": 0.35,
        "method": "GET",
        "path": "/system_stats",
        "headers": {"Connection": "close"},
        "closed": True,
    }


@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("ready", [False, True])
def test_listener_observation_requires_tcp_and_http_readiness(
    monkeypatch: pytest.MonkeyPatch, connected: bool, ready: bool
) -> None:
    """Keep absent listeners cheap while requiring an actual Comfy HTTP response."""
    connections: list[tuple[tuple[str, int], float]] = []
    requests: list[tuple[str, int]] = []
    closed: list[bool] = []

    @contextmanager
    def connect(address: tuple[str, int], *, timeout: float) -> Iterator[None]:
        """Model the external TCP connection boundary and its cleanup."""
        connections.append((address, timeout))
        if not connected:
            raise ConnectionRefusedError("No listener")
        try:
            yield
        finally:
            closed.append(True)

    def respond(*, host: str, port: int) -> bool:
        """Expose the independently tested HTTP result to listener classification."""
        requests.append((host, port))
        return ready

    monkeypatch.setattr(socket, "create_connection", connect)
    monkeypatch.setattr(managed_readiness, "probe_http_ready", respond)
    assert managed_readiness.is_endpoint_listening("localhost", 8188) is (
        connected and ready
    )
    assert connections == [(("localhost", 8188), 0.005)]
    assert requests == ([("localhost", 8188)] if connected else [])
    assert closed == ([True] if connected else [])


def test_wait_for_ready_retries_until_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness polling should retry failed HTTP probes until success."""

    probe_results = iter((False, False, True))
    sleep_calls: list[float] = []
    status_messages: list[str] = []

    monkeypatch.setattr(
        managed_readiness,
        "probe_http_ready",
        lambda *, host, port: next(probe_results),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )
    monotonic_values = iter((0.0, 0.0, 1.0, 1.0, 2.0, 2.0))
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.time.monotonic",
        lambda: next(monotonic_values),
    )

    assert (
        managed_readiness.wait_for_ready(
            "127.0.0.1",
            8188,
            timeout=10.0,
            on_status=status_messages.append,
        )
        is True
    )
    assert sleep_calls == [1.0, 1.0]
    assert status_messages == [
        "Waiting for ComfyUI to become ready…",
        "Waiting for ComfyUI to become ready…",
    ]


def test_wait_for_ready_returns_false_when_canceled() -> None:
    """Readiness polling should stop immediately when cancellation is requested."""

    cancellation = CancellationSource(generation=1)
    cancellation.cancel(reason="test")

    assert (
        managed_readiness.wait_for_ready(
            "127.0.0.1",
            8188,
            timeout=10.0,
            cancellation=cancellation,
        )
        is False
    )
