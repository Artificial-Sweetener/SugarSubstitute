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

"""Tests for listener-scoped websocket connection ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.listener_websocket_connection import (
    ListenerWebsocketConnectionManager,
)
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
)

_CONNECTION_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_websocket_connection.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _Client:
    """Provide the websocket protocol surface for connection-manager tests."""

    def __init__(self, closes: list[str] | None = None) -> None:
        self._closes = closes

    def connect(self, *args: object, **kwargs: object) -> object:
        """Satisfy the websocket client protocol."""

        return None

    def send(self, payload: str) -> object:
        """Satisfy the websocket client protocol."""

        return None

    def recv(self) -> object:
        """Satisfy the websocket client protocol."""

        return ""

    def close(self) -> object:
        """Record close calls when a sink is supplied."""

        if self._closes is not None:
            self._closes.append("closed")
        return None


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_listener_websocket_connection_imports_no_ui_or_listener_boundaries() -> None:
    """Connection ownership must stay independent of UI and listener code."""

    source = _CONNECTION_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_listener_websocket_connection_opens_and_closes_fresh_client() -> None:
    """Fresh listener sessions should connect, send flags, and close with context."""

    client = _Client()
    calls: list[tuple[object, ...]] = []
    manager = ListenerWebsocketConnectionManager(
        client_id="client-1",
        websocket_url="ws://example/ws",
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        connect_timeout_seconds=2.5,
        create_client=lambda: client,
        connect_client=lambda socket, url, timeout: calls.append(
            ("connect", socket, url, timeout)
        ),
        send_feature_flags=lambda socket, client_id: calls.append(
            ("flags", socket, client_id)
        ),
        close_client=lambda socket, workflow_id, generation_run_id, prompt_id: (
            calls.append(("close", socket, workflow_id, generation_run_id, prompt_id))
        ),
    )

    session = manager.open()
    session.close()

    assert session.websocket_client is client
    assert calls == [
        ("connect", client, "ws://example/ws", 2.5),
        ("flags", client, "client-1"),
        ("close", client, "wf-1", "run-1", "pid-1"),
    ]


def test_listener_websocket_connection_uses_preconnected_session_owner() -> None:
    """Preconnected listener sessions should close through the preconnected owner."""

    closes: list[str] = []
    client = _Client(closes)
    preconnected_session = PreconnectedComfyWebsocketSession(
        client_id="client-1",
        websocket_url="ws://example/ws",
        websocket_client=client,
    )
    manager = ListenerWebsocketConnectionManager(
        client_id="client-1",
        websocket_url="ws://example/ws",
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        connect_timeout_seconds=2.5,
        preconnected_session=preconnected_session,
    )

    session = manager.open()
    session.close()
    session.close()

    assert session.websocket_client is client
    assert closes == ["closed"]


def test_listener_websocket_connection_closes_fresh_client_after_open_failure() -> None:
    """Failed fresh opens should close the partially opened websocket client."""

    client = _Client()
    calls: list[tuple[object, ...]] = []
    manager = ListenerWebsocketConnectionManager(
        client_id="client-1",
        websocket_url="ws://example/ws",
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        connect_timeout_seconds=2.5,
        create_client=lambda: client,
        connect_client=_raise_connect_failed,
        send_feature_flags=lambda socket, client_id: calls.append(
            ("flags", socket, client_id)
        ),
        close_client=lambda socket, workflow_id, generation_run_id, prompt_id: (
            calls.append(("close", socket, workflow_id, generation_run_id, prompt_id))
        ),
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        manager.open()

    assert calls == [("close", client, "wf-1", "run-1", "pid-1")]


def _raise_connect_failed(
    _socket: object,
    _url: str,
    _timeout: float,
) -> None:
    """Raise the test connection failure."""

    raise RuntimeError("connect failed")
