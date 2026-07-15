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

"""Send messages to a shared launch-splash session host."""

from __future__ import annotations

import socket

from sugarsubstitute_shared.launch_splash.protocol import (
    SplashSessionMessage,
    encode_splash_session_message,
)
from sugarsubstitute_shared.launch_splash.session import SplashSessionSpec


DEFAULT_SPLASH_CLIENT_TIMEOUT_SECONDS = 2.0
DEFAULT_SPLASH_CLOSE_TIMEOUT_SECONDS = 0.1


class SocketSplashSessionClient:
    """Write launch-splash messages to one local TCP session host."""

    def __init__(
        self,
        spec: SplashSessionSpec,
        *,
        timeout_seconds: float = DEFAULT_SPLASH_CLIENT_TIMEOUT_SECONDS,
    ) -> None:
        """Store the authenticated session endpoint."""

        self._spec = spec
        self._timeout_seconds = timeout_seconds

    @property
    def spec(self) -> SplashSessionSpec:
        """Return the connected splash session spec."""

        return self._spec

    def append_log(self, line: str) -> None:
        """Append one log line to the shared splash."""

        self._send("log", line=line)

    def set_status(self, line: str) -> None:
        """Set the splash status text."""

        self._send("status", line=line)

    def fatal(self, line: str) -> None:
        """Send one fatal startup line to the shared splash."""

        self._send("fatal", line=line)

    def close(self) -> None:
        """Close the shared splash session."""

        try:
            self._send(
                "close",
                line=None,
                timeout_seconds=min(
                    self._timeout_seconds,
                    DEFAULT_SPLASH_CLOSE_TIMEOUT_SECONDS,
                ),
            )
        except OSError:
            return

    def _send(
        self,
        message_type: str,
        *,
        line: str | None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Send one message and wait until the local host consumes it."""

        message = SplashSessionMessage(
            message_type=message_type,
            token=self._spec.token,
            line=line,
        )
        with socket.create_connection(
            (self._spec.host, self._spec.port),
            timeout=self._timeout_seconds
            if timeout_seconds is None
            else timeout_seconds,
        ) as connection:
            connection.sendall(encode_splash_session_message(message))
            connection.shutdown(socket.SHUT_WR)
            connection.recv(1)
