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

import pytest

from substitute.application.execution import CancellationSource
from substitute.infrastructure.comfy import managed_readiness


def test_probe_http_ready_uses_system_stats_endpoint(
    monkeypatch: pytest.MonkeyPatch,
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
            return SimpleNamespace(status=200, read=lambda: b"{}")

        def close(self) -> None:
            observed["closed"] = True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.http.client.HTTPConnection",
        _FakeConnection,
    )
    monkeypatch.setattr(
        managed_readiness,
        "_local_port_is_available",
        lambda **_kwargs: False,
    )

    assert managed_readiness.probe_http_ready(host="127.0.0.1", port=8188) is True
    assert observed == {
        "host": "127.0.0.1",
        "port": 8188,
        "timeout": 0.35,
        "method": "GET",
        "path": "/system_stats",
        "headers": {"Connection": "close"},
        "closed": True,
    }


def test_probe_http_ready_skips_http_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bindable loopback ports should avoid the failed HTTP readiness timeout."""

    observed: list[tuple[str, int]] = []

    class _FakeConnection:
        """Record unexpected HTTP connection attempts."""

        def __init__(self, host: str, port: int, timeout: float) -> None:
            _ = timeout
            observed.append((host, port))

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.http.client.HTTPConnection",
        _FakeConnection,
    )
    monkeypatch.setattr(
        managed_readiness,
        "_local_port_is_available",
        lambda **_kwargs: True,
    )

    assert managed_readiness.probe_http_ready(host="127.0.0.1", port=8188) is False
    assert observed == []


def test_probe_http_ready_does_not_bind_probe_named_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Named hosts should keep the HTTP path to avoid resolver ambiguity."""

    bind_probes: list[tuple[str, int]] = []
    observed: dict[str, object] = {}

    class _FakeConnection:
        """Capture one readiness request for a named host."""

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
            return SimpleNamespace(status=200, read=lambda: b"{}")

        def close(self) -> None:
            observed["closed"] = True

    def record_bind_probe(*, host: str, port: int) -> bool:
        """Record unexpected bind preflights for non-literal hosts."""

        bind_probes.append((host, port))
        return True

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_readiness.http.client.HTTPConnection",
        _FakeConnection,
    )
    monkeypatch.setattr(
        managed_readiness,
        "_local_port_is_available",
        record_bind_probe,
    )

    assert managed_readiness.probe_http_ready(host="localhost", port=8188) is True
    assert bind_probes == []
    assert observed == {
        "host": "localhost",
        "port": 8188,
        "timeout": 0.35,
        "method": "GET",
        "path": "/system_stats",
        "headers": {"Connection": "close"},
        "closed": True,
    }


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
