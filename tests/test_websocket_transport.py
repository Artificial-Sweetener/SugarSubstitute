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

"""Tests for Comfy websocket transport helpers."""

from __future__ import annotations

import ast
import json
import logging
import socket
import types
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.infrastructure.comfy import websocket_transport


def test_websocket_transport_module_keeps_infrastructure_boundary() -> None:
    """Websocket transport must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "websocket_transport.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


def test_create_websocket_client_uses_websocket_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transport client construction should be the only websocket factory owner."""

    created: list[object] = []

    class _FakeWebSocket:
        """Record construction through the patched websocket factory."""

        def __init__(self) -> None:
            created.append(self)

        def connect(self, *_args: object, **_kwargs: object) -> object:
            return None

        def send(self, _payload: str) -> object:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> object:
            return None

    monkeypatch.setattr(
        cast(Any, websocket_transport).websocket,
        "WebSocket",
        _FakeWebSocket,
    )

    client = websocket_transport.create_websocket_client()

    assert client is created[0]


def test_connect_websocket_passes_timeout_when_supported() -> None:
    """Connection should use websocket-client's timeout keyword when available."""

    calls: list[tuple[str, float | None]] = []

    class _Client:
        def connect(self, url: str, *, timeout: float | None = None) -> None:
            calls.append((url, timeout))

        def send(self, _payload: str) -> None:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            return None

    websocket_transport.connect_websocket(
        cast(websocket_transport.WebSocketClient, _Client()),
        websocket_url="ws://example/ws",
        connect_timeout_seconds=2.5,
    )

    assert calls == [("ws://example/ws", 2.5)]


def test_connect_websocket_falls_back_when_timeout_keyword_is_unsupported() -> None:
    """Legacy websocket clients should still connect without timeout kwargs."""

    calls: list[tuple[object, ...]] = []

    class _Client:
        def connect(self, *args: object, **kwargs: object) -> None:
            calls.append(args)
            if kwargs:
                raise TypeError("unexpected timeout")

        def send(self, _payload: str) -> None:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            return None

    websocket_transport.connect_websocket(
        _Client(),
        websocket_url="ws://example/ws",
        connect_timeout_seconds=2.5,
    )

    assert calls == [("ws://example/ws",), ("ws://example/ws",)]


def test_send_preview_feature_flags_sends_json_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Preview metadata support should be announced as the first client message."""

    sent: list[str] = []

    class _Client:
        def connect(self, *_args: object, **_kwargs: object) -> None:
            return None

        def send(self, payload: str) -> None:
            sent.append(payload)

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            return None

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.websocket_transport",
    ):
        websocket_transport.send_preview_feature_flags(_Client(), client_id="client-1")

    assert json.loads(sent[0]) == {
        "type": "feature_flags",
        "data": {"supports_preview_metadata": True},
    }
    assert "Sent Comfy websocket feature flags" in caplog.text


def test_close_websocket_logs_close_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Close failures should stay diagnostic-only and preserve listener context."""

    class _Client:
        def connect(self, *_args: object, **_kwargs: object) -> None:
            return None

        def send(self, _payload: str) -> None:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            raise RuntimeError("close failed")

    with caplog.at_level(
        logging.ERROR,
        logger="sugarsubstitute.infrastructure.comfy.websocket_transport",
    ):
        websocket_transport.close_websocket(
            _Client(),
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )

    assert "Failed to close websocket client cleanly" in caplog.text
    assert "workflow_id=wf-1" in caplog.text
    assert "prompt_id=pid-1" in caplog.text


def test_preconnected_session_closes_client_once_on_explicit_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preconnected sessions should be idempotent close owners."""

    closes: list[str] = []

    class _Client:
        def connect(self, *_args: object, **_kwargs: object) -> None:
            return None

        def send(self, _payload: str) -> None:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            closes.append("closed")

    monkeypatch.setattr(
        cast(Any, websocket_transport).websocket,
        "WebSocket",
        _Client,
    )

    session = websocket_transport.PreconnectedComfyWebsocketSession.connect(
        client_id="client-1",
        websocket_url="ws://example/ws",
        connect_timeout_seconds=1.0,
    )
    session.close()
    session.close()

    assert closes == ["closed"]


def test_preconnected_session_closes_client_after_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed preconnection should close the partially opened websocket."""

    closes: list[str] = []

    class _Client:
        def connect(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("connect failed")

        def send(self, _payload: str) -> None:
            return None

        def recv(self) -> object:
            return ""

        def close(self) -> None:
            closes.append("closed")

    monkeypatch.setattr(
        cast(Any, websocket_transport).websocket,
        "WebSocket",
        _Client,
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        websocket_transport.PreconnectedComfyWebsocketSession.connect(
            client_id="client-1",
            websocket_url="ws://example/ws",
            connect_timeout_seconds=1.0,
        )

    assert closes == ["closed"]


def test_set_receive_timeout_uses_supported_client_method() -> None:
    """Receive timeout application should be optional by client capability."""

    timeouts: list[float] = []

    client = types.SimpleNamespace(
        settimeout=lambda value: timeouts.append(value),
        connect=lambda *_args, **_kwargs: None,
        send=lambda _payload: None,
        recv=lambda: "",
        close=lambda: None,
    )

    websocket_transport.set_receive_timeout(client, 3.5)
    websocket_transport.set_receive_timeout(
        types.SimpleNamespace(
            connect=lambda *_args, **_kwargs: None,
            send=lambda _payload: None,
            recv=lambda: "",
            close=lambda: None,
        ),
        3.5,
    )

    assert timeouts == [3.5]


def test_error_classification_handles_timeouts_and_nested_disconnects() -> None:
    """Transport error classification should preserve listener failure behavior."""

    websocket_timeout = type("WebSocketTimeoutException", (Exception,), {})
    closed_error = type("WebSocketConnectionClosedException", (Exception,), {})
    bad_status = type("WebSocketBadStatusException", (Exception,), {})
    nested = RuntimeError("wrapper")
    nested.__cause__ = closed_error("closed")

    assert websocket_transport.is_timeout_error(TimeoutError("timeout"))
    assert websocket_transport.is_timeout_error(socket.timeout("timeout"))
    assert websocket_transport.is_timeout_error(websocket_timeout("timeout"))
    assert not websocket_transport.is_timeout_error(RuntimeError("other"))
    assert websocket_transport.is_disconnect_error(ConnectionError("closed"))
    assert websocket_transport.is_disconnect_error(ConnectionResetError("reset"))
    assert websocket_transport.is_disconnect_error(ConnectionAbortedError("aborted"))
    assert websocket_transport.is_disconnect_error(closed_error("closed"))
    assert websocket_transport.is_disconnect_error(bad_status("bad"))
    assert websocket_transport.is_disconnect_error(nested)
    assert not websocket_transport.is_disconnect_error(RuntimeError("other"))
