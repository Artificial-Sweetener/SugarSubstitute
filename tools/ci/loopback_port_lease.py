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

"""Reserve loopback ports until qualification children are ready to bind."""

from __future__ import annotations

from collections.abc import Iterable
import socket
from types import TracebackType

_LOOPBACK_HOST = "127.0.0.1"
_QUALIFICATION_PORTS = range(20_000, 30_000)


class LoopbackPortLeaseError(RuntimeError):
    """Report that no candidate qualification port could be reserved."""


class LoopbackPortLease:
    """Own one loopback reservation until an explicit one-shot handoff."""

    def __init__(self, reservation: socket.socket, port: int) -> None:
        """Retain the bound socket and its validated port."""

        self._reservation: socket.socket | None = reservation
        self._port = port

    @classmethod
    def acquire(
        cls,
        *,
        candidate_ports: Iterable[int] = _QUALIFICATION_PORTS,
    ) -> LoopbackPortLease:
        """Reserve the first available non-ephemeral qualification port."""

        attempted_port = False
        last_error: OSError | None = None
        for port in candidate_ports:
            attempted_port = True
            if not 1 <= port <= 65_535:
                raise ValueError(f"Loopback port is outside the valid range: {port}")
            reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                reservation.bind((_LOOPBACK_HOST, port))
                reservation.listen(1)
            except OSError as error:
                reservation.close()
                last_error = error
                continue
            return cls(reservation, port)
        if not attempted_port:
            raise LoopbackPortLeaseError("No loopback candidate ports were provided.")
        raise LoopbackPortLeaseError(
            "Could not reserve any non-ephemeral loopback qualification port."
        ) from last_error

    @property
    def port(self) -> int:
        """Return the reserved port without releasing its socket."""

        return self._port

    def release_for_handoff(self) -> int:
        """Release the port exactly once immediately before its child binds."""

        if self._reservation is None:
            raise LoopbackPortLeaseError(
                "Loopback qualification port has already been released."
            )
        self._reservation.close()
        self._reservation = None
        return self._port

    def close(self) -> None:
        """Release an unconsumed reservation during failure cleanup."""

        if self._reservation is not None:
            self._reservation.close()
            self._reservation = None

    def __enter__(self) -> LoopbackPortLease:
        """Retain this lease for one qualification lifetime."""

        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release any reservation that never reached child handoff."""

        del exception_type, exception, traceback
        self.close()


__all__ = ["LoopbackPortLease", "LoopbackPortLeaseError"]
