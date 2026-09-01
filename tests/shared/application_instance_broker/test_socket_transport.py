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

"""Verify socket transport shutdown behavior shared by Linux and macOS."""

import socket

from sugarsubstitute_shared.application_instance_socket import (
    SocketInstanceConnection,
)


def test_connection_close_wakes_peer_blocked_on_receive() -> None:
    """Signal supervisor loss to a peer before releasing the socket handle."""

    owned_socket, peer_socket = socket.socketpair()
    connection = SocketInstanceConnection(owned_socket)
    peer_socket.settimeout(2.0)
    try:
        connection.close()
        assert peer_socket.recv(1) == b""
    finally:
        peer_socket.close()
