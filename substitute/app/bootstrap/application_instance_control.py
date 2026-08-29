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

"""Serve graceful shutdown requests from duplicate application invocations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from sugarsubstitute_shared.application_instance_control import (
    application_instance_control_name,
)


ShutdownRequest = Callable[[object | None], None]
_ACTIVE_SERVER: ApplicationInstanceControlServer | None = None


class ApplicationInstanceControlServer(QObject):
    """Own the per-instance local server and forward authenticated local actions."""

    def __init__(self, install_root: Path) -> None:
        """Start a user-only server for one installation identity."""

        super().__init__()
        self._shutdown_request: ShutdownRequest | None = None
        self._shutdown_pending = False
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        server_name = application_instance_control_name(install_root)
        if not self._server.listen(server_name):
            QLocalServer.removeServer(server_name)
            if not self._server.listen(server_name):
                raise RuntimeError(
                    f"Application instance control server could not listen: {server_name}"
                )

    def bind_shutdown_request(self, request: ShutdownRequest) -> None:
        """Bind coordinated shutdown and replay one request received during startup."""

        self._shutdown_request = request
        if self._shutdown_pending:
            self._shutdown_pending = False
            request(None)

    def close(self) -> None:
        """Stop accepting application-instance control requests."""

        self._server.close()

    def _accept_connections(self) -> None:
        """Attach request parsing to every pending local connection."""

        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda active=socket: self._handle_request(active))
            if socket.bytesAvailable():
                self._handle_request(socket)

    def _handle_request(self, socket: QLocalSocket) -> None:
        """Acknowledge one valid request before scheduling coordinated shutdown."""

        if not socket.canReadLine():
            return
        request = cast(bytes, socket.readLine().data()).strip()
        if request != b"shutdown":
            socket.write(b"rejected\n")
            socket.flush()
            return
        socket.write(b"accepted\n")
        socket.flush()
        socket.waitForBytesWritten(1000)
        if self._shutdown_request is None:
            self._shutdown_pending = True
            return
        self._shutdown_request(None)


def start_application_instance_control(
    install_root: Path,
) -> ApplicationInstanceControlServer:
    """Start and retain the active application's local control server."""

    global _ACTIVE_SERVER
    stop_application_instance_control()
    server = ApplicationInstanceControlServer(install_root)
    _ACTIVE_SERVER = server
    return server


def bind_application_instance_shutdown_request(request: ShutdownRequest) -> None:
    """Bind the active control server to the composed shutdown coordinator."""

    if _ACTIVE_SERVER is not None:
        _ACTIVE_SERVER.bind_shutdown_request(request)


def stop_application_instance_control() -> None:
    """Stop and release the active local control server idempotently."""

    global _ACTIVE_SERVER
    server = _ACTIVE_SERVER
    _ACTIVE_SERVER = None
    if server is not None:
        server.close()


__all__ = [
    "ApplicationInstanceControlServer",
    "bind_application_instance_shutdown_request",
    "start_application_instance_control",
    "stop_application_instance_control",
]
