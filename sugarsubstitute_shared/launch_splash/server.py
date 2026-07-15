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

"""Host the local message endpoint for a shared launch-splash session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import socketserver
import threading
from typing import Protocol

from sugarsubstitute_shared.launch_splash.protocol import (
    MAX_SPLASH_MESSAGE_BYTES,
    SplashSessionMessage,
    SplashSessionMessageError,
    decode_splash_session_message,
)
from sugarsubstitute_shared.launch_splash.session import (
    DEFAULT_SPLASH_HOST,
    SplashSessionSpec,
    create_splash_session_spec,
)


class SplashSessionMessageHandler(Protocol):
    """Handle validated splash session messages."""

    def handle_message(self, message: SplashSessionMessage) -> None:
        """Process one authenticated splash session message."""


@dataclass(frozen=True, slots=True)
class _ServerContext:
    """Carry immutable server dispatch dependencies."""

    expected_token: str
    message_handler: SplashSessionMessageHandler
    on_invalid_message: Callable[[SplashSessionMessageError], None] | None


class SplashSessionServer:
    """Run a local TCP endpoint for one splash session."""

    def __init__(
        self,
        *,
        message_handler: SplashSessionMessageHandler,
        host: str = DEFAULT_SPLASH_HOST,
        token: str | None = None,
        on_invalid_message: Callable[[SplashSessionMessageError], None] | None = None,
    ) -> None:
        """Create a stopped splash session server."""

        self._server = _ThreadingSplashTcpServer(
            (host, 0), _SplashSessionRequestHandler
        )
        port = int(self._server.server_address[1])
        self._spec = create_splash_session_spec(
            host=host,
            port=port,
            token=token,
        )
        self._server.context = _ServerContext(
            expected_token=self._spec.token,
            message_handler=message_handler,
            on_invalid_message=on_invalid_message,
        )
        self._thread: threading.Thread | None = None

    @property
    def spec(self) -> SplashSessionSpec:
        """Return the session spec clients need to connect."""

        return self._spec

    def start(self) -> None:
        """Start accepting local splash session messages."""

        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="sugarsubstitute-splash-session",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        """Stop accepting messages and release the local endpoint."""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


class _ThreadingSplashTcpServer(socketserver.ThreadingTCPServer):
    """TCP server carrying splash session dispatch context."""

    allow_reuse_address = True
    context: _ServerContext


class _SplashSessionRequestHandler(socketserver.BaseRequestHandler):
    """Decode one short-lived splash session connection."""

    server: _ThreadingSplashTcpServer

    def handle(self) -> None:
        """Read and dispatch one authenticated splash session message."""

        raw_message = self.request.recv(MAX_SPLASH_MESSAGE_BYTES + 1)
        try:
            message = decode_splash_session_message(
                raw_message,
                expected_token=self.server.context.expected_token,
            )
        except SplashSessionMessageError as error:
            if self.server.context.on_invalid_message is not None:
                self.server.context.on_invalid_message(error)
            return
        self.server.context.message_handler.handle_message(message)
