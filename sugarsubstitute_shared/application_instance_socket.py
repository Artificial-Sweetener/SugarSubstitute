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

"""Adapt framed application-instance messages to local sockets."""

from __future__ import annotations

import os
import socket
import struct
from typing import cast

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceEndpoint,
)


class SocketInstanceConnection:
    """Frame messages over one local stream socket."""

    def __init__(self, connection: socket.socket) -> None:
        """Retain one connected stream socket."""

        self._connection = connection

    def send_frame(self, payload: bytes) -> None:
        """Send one length-prefixed frame."""

        self._connection.sendall(struct.pack("!I", len(payload)) + payload)

    def receive_frame(self, maximum_size: int) -> bytes:
        """Receive one bounded length-prefixed frame."""

        size = struct.unpack("!I", self._receive_exact(4))[0]
        if size > maximum_size:
            raise ValueError("Application instance message exceeds its size limit.")
        return self._receive_exact(size)

    def close(self) -> None:
        """Close the underlying socket."""

        self._connection.close()

    def peer_is_current_user(self) -> bool:
        """Return whether Linux kernel credentials identify this local user."""

        if not hasattr(socket, "SO_PEERCRED") or not hasattr(os, "getuid"):
            return True
        credentials = self._connection.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize("3i"),
        )
        _pid, user_id, _group_id = struct.unpack("3i", credentials)
        return bool(user_id == os.getuid())

    def _receive_exact(self, size: int) -> bytes:
        """Read one complete frame segment or fail on disconnect."""

        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = self._connection.recv(remaining)
            if not chunk:
                raise OSError("Application instance connection closed mid-message.")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


class SocketInstanceListener:
    """Accept framed connections from one bound local socket."""

    def __init__(self, listener: socket.socket) -> None:
        """Retain an already-listening socket."""

        self._listener = listener

    def accept(self) -> ApplicationInstanceConnection:
        """Accept and authorize one same-user local connection."""

        connection, _address = self._listener.accept()
        wrapped = SocketInstanceConnection(connection)
        if not wrapped.peer_is_current_user():
            wrapped.close()
            raise PermissionError("Application instance peer belongs to another user.")
        return wrapped

    def close(self) -> None:
        """Close the listening socket."""

        self._listener.close()


def bind_socket_listener(
    endpoint: ApplicationInstanceEndpoint,
) -> SocketInstanceListener:
    """Bind one fileless local socket endpoint."""

    if endpoint.transport == "abstract-unix":
        unix_family = cast(int, getattr(socket, "AF_UNIX"))
        listener = socket.socket(unix_family, socket.SOCK_STREAM)
        listener.bind(f"\0{endpoint.address}")
    else:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        if endpoint.port is None:
            raise ValueError("Loopback endpoint requires a port.")
        listener.bind((endpoint.address, endpoint.port))
    listener.listen(32)
    return SocketInstanceListener(listener)


def connect_socket_endpoint(
    endpoint: ApplicationInstanceEndpoint,
) -> SocketInstanceConnection:
    """Connect to one local socket endpoint."""

    family = (
        cast(int, getattr(socket, "AF_UNIX"))
        if endpoint.transport == "abstract-unix"
        else socket.AF_INET
    )
    connection = socket.socket(family, socket.SOCK_STREAM)
    if endpoint.transport == "abstract-unix":
        connection.connect(f"\0{endpoint.address}")
    else:
        if endpoint.port is None:
            raise ValueError("Loopback endpoint requires a port.")
        connection.connect((endpoint.address, endpoint.port))
    wrapped = SocketInstanceConnection(connection)
    if not wrapped.peer_is_current_user():
        wrapped.close()
        raise PermissionError("Application instance owner belongs to another user.")
    return wrapped


__all__ = [
    "SocketInstanceConnection",
    "SocketInstanceListener",
    "bind_socket_listener",
    "connect_socket_endpoint",
]
