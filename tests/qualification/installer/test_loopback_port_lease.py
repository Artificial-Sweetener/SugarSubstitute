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

"""Prove qualification loopback ports remain owned until child handoff."""

from __future__ import annotations

import socket

import pytest

from tools.ci.loopback_port_lease import (
    LoopbackPortLease,
    LoopbackPortLeaseError,
)


def _bind_loopback(port: int) -> socket.socket:
    """Bind one test-owned loopback listener and return its lifetime owner."""

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)
    return listener


def test_lease_prevents_reuse_until_explicit_handoff() -> None:
    """Expensive setup must retain exclusive ownership of its endpoint."""

    with LoopbackPortLease.acquire() as lease:
        with pytest.raises(OSError):
            _bind_loopback(lease.port)

        handed_off_port = lease.release_for_handoff()
        with _bind_loopback(handed_off_port):
            pass

        with pytest.raises(LoopbackPortLeaseError, match="already been released"):
            lease.release_for_handoff()


def test_lease_skips_an_endpoint_owned_by_another_listener() -> None:
    """Concurrent qualification resources must select distinct endpoints."""

    with LoopbackPortLease.acquire() as occupied:
        with LoopbackPortLease.acquire(
            candidate_ports=(occupied.port, *range(20_000, 30_000))
        ) as lease:
            assert lease.port != occupied.port


def test_lease_context_releases_an_unconsumed_reservation() -> None:
    """Setup failure must not leak a port that never reached handoff."""

    with LoopbackPortLease.acquire() as lease:
        port = lease.port

    with _bind_loopback(port):
        pass
