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

"""Verify stage progress remains optional and compatible across splash hosts."""

from __future__ import annotations

import json

import pytest

from sugarsubstitute_shared.launch_splash.progress import SplashProgress
from sugarsubstitute_shared.launch_splash.protocol import (
    SplashSessionMessage,
    SplashSessionMessageError,
    decode_splash_session_message,
    encode_splash_session_message,
)


def test_status_progress_round_trip_preserves_existing_status_shape() -> None:
    """Carry measured stage units beside text understood by existing hosts."""
    message = SplashSessionMessage(
        "status", "token", "Preparing workspace", progress=SplashProgress(2, 5)
    )
    encoded = encode_splash_session_message(message)
    payload = json.loads(encoded)
    assert payload["type"] == "status"
    assert payload["line"] == "Preparing workspace"
    assert payload["progress"] == {"completed": 2, "total": 5}
    assert decode_splash_session_message(encoded, expected_token="token") == message


def test_legacy_status_has_no_fabricated_completion() -> None:
    """Keep status-only hosts and clients valid without inventing work units."""
    message = SplashSessionMessage("status", "token", "Starting")
    encoded = encode_splash_session_message(message)
    assert "progress" not in json.loads(encoded)
    assert (
        decode_splash_session_message(encoded, expected_token="token").progress is None
    )


@pytest.mark.parametrize(
    "completed,total",
    [(-1, 5), (6, 5), (0, 0), (True, 5), (1, False), (1.5, 5), (1, "5")],
)
def test_untrusted_progress_rejects_invalid_units(
    completed: object, total: object
) -> None:
    """Reject numeric coercion and invalid ranges at the wire boundary."""
    encoded = json.dumps(
        {
            "type": "status",
            "token": "token",
            "line": "Starting",
            "progress": {"completed": completed, "total": total},
        }
    ).encode()
    with pytest.raises(SplashSessionMessageError):
        decode_splash_session_message(encoded, expected_token="token")


@pytest.mark.parametrize("kind", ["log", "fatal", "activity", "activate", "close"])
def test_progress_is_owned_only_by_status_messages(kind: str) -> None:
    """Prevent diagnostic output and terminal controls from advancing completion."""
    encoded = json.dumps(
        {
            "type": kind,
            "token": "token",
            "line": "Text",
            "progress": {"completed": 1, "total": 2},
        }
    ).encode()
    with pytest.raises(SplashSessionMessageError):
        decode_splash_session_message(encoded, expected_token="token")


def test_progress_crosses_the_real_socket_boundary() -> None:
    """Acknowledge applied stage data through the production client and server."""
    from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
    from sugarsubstitute_shared.launch_splash.server import SplashSessionServer

    received: list[SplashSessionMessage] = []

    class Handler:
        """Record messages after production authentication and decoding."""

        def handle_message(self, message: SplashSessionMessage) -> None:
            """Retain the applied status before the server acknowledges it."""
            received.append(message)

    server = SplashSessionServer(message_handler=Handler(), token="x" * 32)
    server.start()
    try:
        client = SocketSplashSessionClient(server.spec)
        client.set_progress(SplashProgress(3, 5), status="Preparing workspace")
        assert received == [
            SplashSessionMessage(
                "status", "x" * 32, "Preparing workspace", progress=SplashProgress(3, 5)
            )
        ]
    finally:
        server.close()
