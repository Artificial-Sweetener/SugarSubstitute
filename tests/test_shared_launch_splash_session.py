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

"""Tests for shared launch-splash session primitives."""

from __future__ import annotations

from threading import Event
from typing import Any

import pytest

from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    SplashSessionMessage,
    SplashSessionMessageError,
    SplashSessionServer,
    create_splash_session_spec,
    decode_splash_session_message,
    encode_splash_session_message,
    splash_session_args,
    splash_session_from_args,
)
from sugarsubstitute_shared.launch_splash.client import (
    DEFAULT_SPLASH_CLOSE_TIMEOUT_SECONDS,
)


def test_splash_session_args_round_trip_without_exposing_defaults() -> None:
    """Session specs should serialize into explicit app launch arguments."""

    spec = create_splash_session_spec(
        host="127.0.0.1",
        port=49152,
        token="x" * 32,
        host_pid=1234,
    )

    parsed = splash_session_from_args(["main.py", *splash_session_args(spec)])

    assert parsed == spec


def test_splash_session_args_reject_incomplete_session() -> None:
    """App startup should reject partial launcher-provided session details."""

    with pytest.raises(ValueError, match="complete set"):
        splash_session_from_args(
            [
                "main.py",
                "--splash-session-endpoint=127.0.0.1:49152",
                "--splash-session-token=" + ("x" * 32),
            ]
        )


def test_splash_session_spec_rejects_nonlocal_hosts() -> None:
    """Splash handoff IPC must stay bound to a local endpoint."""

    with pytest.raises(ValueError, match="local"):
        create_splash_session_spec(
            host="192.0.2.1",
            port=49152,
            token="x" * 32,
            host_pid=1234,
        )


def test_splash_session_message_round_trips_with_token() -> None:
    """Session messages should decode only with the expected token."""

    encoded = encode_splash_session_message(
        SplashSessionMessage(
            message_type="log",
            token="secret-token",
            line="Checking for updates.",
        )
    )

    assert decode_splash_session_message(encoded, expected_token="secret-token") == (
        SplashSessionMessage(
            message_type="log",
            token="secret-token",
            line="Checking for updates.",
        )
    )


def test_splash_session_message_rejects_wrong_token() -> None:
    """Splash host should fail closed on unauthenticated messages."""

    encoded = encode_splash_session_message(
        SplashSessionMessage(
            message_type="close",
            token="wrong-token",
        )
    )

    with pytest.raises(SplashSessionMessageError, match="invalid"):
        decode_splash_session_message(encoded, expected_token="right-token")


def test_socket_splash_session_client_delivers_messages_to_server() -> None:
    """Socket client and server should carry authenticated splash messages."""

    received: list[SplashSessionMessage] = []
    delivered = Event()
    handler = _RecordingHandler(received, delivered)
    server = SplashSessionServer(message_handler=handler, token="x" * 32)
    server.start()
    try:
        client = SocketSplashSessionClient(server.spec)
        client.append_log("Checking for updates.")
        client.set_status("Installing update.")
        client.close()
        assert delivered.wait(timeout=2.0)
    finally:
        server.close()

    assert received == [
        SplashSessionMessage(
            message_type="log",
            token="x" * 32,
            line="Checking for updates.",
        ),
        SplashSessionMessage(
            message_type="status",
            token="x" * 32,
            line="Installing update.",
        ),
        SplashSessionMessage(message_type="close", token="x" * 32),
    ]


def test_socket_splash_session_close_ignores_unresponsive_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown splash close should not raise when the local session is gone."""

    spec = create_splash_session_spec(
        host="127.0.0.1",
        port=49152,
        token="x" * 32,
        host_pid=1234,
    )
    timeouts: list[float | None] = []

    def _raise_timeout(
        _address: tuple[str, int],
        *,
        timeout: float | None = None,
        **_kwargs: Any,
    ) -> object:
        """Record the timeout used for close and simulate an unresponsive host."""

        timeouts.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr("socket.create_connection", _raise_timeout)

    SocketSplashSessionClient(spec).close()

    assert timeouts == [DEFAULT_SPLASH_CLOSE_TIMEOUT_SECONDS]


def test_socket_splash_session_non_close_writes_still_report_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only close is best-effort; startup status writes should still fail loudly."""

    spec = create_splash_session_spec(
        host="127.0.0.1",
        port=49152,
        token="x" * 32,
        host_pid=1234,
    )

    def _raise_timeout(
        _address: tuple[str, int],
        *,
        timeout: float | None = None,
        **_kwargs: Any,
    ) -> object:
        """Simulate an unresponsive splash session."""

        _ = timeout
        raise TimeoutError("timed out")

    monkeypatch.setattr("socket.create_connection", _raise_timeout)

    with pytest.raises(TimeoutError):
        SocketSplashSessionClient(spec).set_status("Starting.")


def test_splash_session_server_reports_invalid_messages() -> None:
    """Server should reject invalid token messages without dispatching them."""

    received: list[SplashSessionMessage] = []
    errors: list[SplashSessionMessageError] = []
    server = SplashSessionServer(
        message_handler=_RecordingHandler(received, Event()),
        token="x" * 32,
        on_invalid_message=errors.append,
    )
    server.start()
    try:
        wrong_spec = create_splash_session_spec(
            host=server.spec.host,
            port=server.spec.port,
            token="y" * 32,
            host_pid=server.spec.host_pid,
        )
        SocketSplashSessionClient(wrong_spec).append_log("Unauthorized.")
    finally:
        server.close()

    assert received == []
    assert len(errors) == 1
    assert "invalid" in str(errors[0])


class _RecordingHandler:
    """Record splash session messages for tests."""

    def __init__(
        self,
        received: list[SplashSessionMessage],
        delivered: Event,
    ) -> None:
        """Store mutable test result containers."""

        self._received = received
        self._delivered = delivered

    def handle_message(self, message: SplashSessionMessage) -> None:
        """Record one delivered splash session message."""

        self._received.append(message)
        if message.message_type == "close":
            self._delivered.set()
