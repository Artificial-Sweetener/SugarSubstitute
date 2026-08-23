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

"""Tests for Cube Library websocket event parsing and listener lifecycle."""

from __future__ import annotations

import logging

import pytest

from substitute.application.execution import (
    CancellationSource,
    DirectExecutionDispatcher,
    ExecutionContext,
    TaskIdentity,
)
from substitute.infrastructure.comfy.cube_library_event_listener import (
    CubeLibraryEventListener,
    _is_expected_disconnect,
    parse_cube_library_changed_update,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.execution.long_lived_task import (
    LongLivedTaskHandle,
    LongLivedWork,
)


class _BlockingWebSocket:
    """Block in recv until the listener is stopped."""

    def __init__(self) -> None:
        """Initialize websocket state."""

        self.closed = False

    def connect(self, _url: str, timeout: float | None = None) -> None:
        """Accept one test connection."""

        _ = timeout

    def settimeout(self, _timeout: float) -> None:
        """Accept receive timeout configuration."""

    def recv(self) -> str:
        """Raise timeout repeatedly so the listener can observe stop requests."""

        raise TimeoutError("timed out")

    def close(self) -> None:
        """Record close."""

        self.closed = True


class _RefusingWebSocket:
    """Refuse connections until the listener test stops the reconnect loop."""

    def __init__(
        self,
        *,
        attempts: list[int],
        cancellation: CancellationSource,
        stop_after: int,
    ) -> None:
        """Store shared attempt state and listener stop target."""

        self._attempts = attempts
        self._cancellation = cancellation
        self._stop_after = stop_after

    def connect(self, _url: str, timeout: float | None = None) -> None:
        """Raise a connection refusal and stop the loop after enough attempts."""

        del timeout
        self._attempts[0] += 1
        if self._attempts[0] > self._stop_after:
            pytest.fail("listener continued reconnecting after test cancellation")
        if self._attempts[0] >= self._stop_after:
            self._cancellation.cancel(reason="test_complete")
        raise ConnectionRefusedError(10061, "connection refused")

    def close(self) -> None:
        """Accept close calls after failed connects."""


def test_parse_cube_library_changed_update_accepts_schema_version_one() -> None:
    """Version 1 Cube Library change payloads should parse."""

    update = parse_cube_library_changed_update(
        {
            "schemaVersion": 1,
            "catalogRevision": "rev-2",
            "previousCatalogRevision": "rev-1",
            "generatedAt": "2026-05-15T19:00:00+00:00",
            "reason": "catalog-revision-changed",
        }
    )

    assert update is not None
    assert update.catalog_revision == "rev-2"
    assert update.previous_catalog_revision == "rev-1"


def test_parse_cube_library_changed_update_ignores_unsupported_schema() -> None:
    """Unsupported schema versions should be ignored."""

    update = parse_cube_library_changed_update(
        {
            "schemaVersion": 99,
            "catalogRevision": "rev-2",
            "previousCatalogRevision": "rev-1",
            "generatedAt": "2026-05-15T19:00:00+00:00",
            "reason": "catalog-revision-changed",
        }
    )

    assert update is None


def test_listener_shutdown_stops_reconnect_attempts() -> None:
    """Stopping the listener should end the background receive loop."""

    websocket = _BlockingWebSocket()
    listener = CubeLibraryEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda _update: None,
        websocket_factory=lambda: websocket,
        task_factory=_long_lived_task_factory,
        receive_timeout_seconds=0.01,
    )

    listener.start()
    listener.stop()

    assert not listener.is_running
    assert websocket.closed


def test_listener_classifies_socket_disconnects_as_expected() -> None:
    """Common websocket socket closures should reconnect without tracebacks."""

    assert _is_expected_disconnect(ConnectionResetError("connection reset"))


def test_listener_warns_once_for_repeated_expected_disconnects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Expected reconnect loops should not emit repeated warnings."""

    attempts = [0]
    cancellation = CancellationSource(generation=0)
    listener = CubeLibraryEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda _update: None,
        websocket_factory=lambda: _RefusingWebSocket(
            attempts=attempts,
            cancellation=cancellation,
            stop_after=3,
        ),
        backoff_seconds=(0.0,),
    )

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.cube_library_event_listener",
    ):
        listener._run(cancellation)  # noqa: SLF001

    reconnect_records = [
        record
        for record in caplog.records
        if record.message.startswith(
            "Cube Library websocket listener disconnected; reconnecting"
        )
    ]
    assert [record.levelno for record in reconnect_records] == [
        logging.WARNING,
        logging.INFO,
    ]
    assert attempts == [3]


def _long_lived_task_factory(
    identity: TaskIdentity,
    context: ExecutionContext,
    work: LongLivedWork[None],
    thread_name: str,
) -> LongLivedTaskHandle[None]:
    """Create a real long-lived task handle for listener lifecycle tests."""

    return LongLivedTaskHandle(
        identity=identity,
        context=context,
        work=work,
        dispatcher=DirectExecutionDispatcher(),
        thread_name=thread_name,
    )
