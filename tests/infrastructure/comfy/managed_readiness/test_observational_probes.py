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

"""Protect server-port ownership from client-side readiness checks."""

from __future__ import annotations

import socket

import pytest

from substitute.infrastructure.comfy.managed_readiness import is_endpoint_listening
from substitute.infrastructure.comfy.managed_readiness import probe_http_ready


@pytest.mark.parametrize("probe", ["readiness", "ownership"])
def test_absent_endpoint_probe_never_claims_server_address(
    probe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observe native bind calls while checking a real, unserved loopback endpoint.

    A client bind can exclude the server during concurrent startup even when it
    lasts only one scheduling interval. Neither readiness consumer may take
    ownership of the destination address as a preflight optimization.
    """
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    bindings: list[tuple[str, int]] = []
    native_bind = socket.socket.bind

    def observe_bind(connection: socket.socket, address: tuple[str, int]) -> None:
        """Retain real OS behavior while recording address ownership attempts."""
        bindings.append(address)
        native_bind(connection, address)

    monkeypatch.setattr(socket.socket, "bind", observe_bind)
    if probe == "readiness":
        ready = probe_http_ready(host="127.0.0.1", port=port)
    else:
        ready = is_endpoint_listening("127.0.0.1", port)
    assert ready is False
    assert bindings == [], "A readiness client claimed the server's address"
