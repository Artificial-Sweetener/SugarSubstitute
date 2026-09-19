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

"""Own Linux application-instance election through the desktop session bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
import logging
from typing import Protocol, cast


_DO_NOT_QUEUE = 4
_PRIMARY_OWNER = 1
_ALREADY_OWNER = 4
_LOGGER = logging.getLogger(__name__)


class LinuxSessionBusElection(str, Enum):
    """Describe whether D-Bus elected this process or requires fallback."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True)
class LinuxSessionBusClaim:
    """Retain the D-Bus connection that owns one well-known session name."""

    connection: _DbusConnection
    message_bus: _MessageBus
    name: str
    _closed: bool = field(default=False, init=False)

    def close(self) -> None:
        """Synchronously release the well-known name, then disconnect."""

        if self._closed:
            return
        self._closed = True
        try:
            self.connection.send_and_get_reply(self.message_bus.ReleaseName(self.name))
        except Exception:
            _LOGGER.debug(
                "Linux session D-Bus disconnected during name release",
                extra={"instance_bus_name": self.name},
                exc_info=True,
            )
        finally:
            self.connection.close()


@dataclass(frozen=True, slots=True)
class LinuxSessionBusResult:
    """Return one Linux election outcome and any retained owner claim."""

    election: LinuxSessionBusElection
    claim: LinuxSessionBusClaim | None = None


class _DbusReply(Protocol):
    """Describe the response fields needed from Jeepney."""

    body: tuple[object, ...]


class _DbusConnection(Protocol):
    """Describe the blocking Jeepney connection retained by the supervisor."""

    def send_and_get_reply(self, message: object) -> _DbusReply:
        """Send one bus request and receive its response."""

    def close(self) -> None:
        """Close the session-bus connection."""


class _MessageBus(Protocol):
    """Describe the Jeepney bus message generator used for name election."""

    def RequestName(self, name: str, flags: int = 0) -> object:
        """Build one well-known-name request."""

    def ReleaseName(self, name: str) -> object:
        """Build one well-known-name release request."""


def acquire_linux_session_bus(identity: str) -> LinuxSessionBusResult:
    """Atomically request one private well-known name or select socket fallback."""

    connection: _DbusConnection | None = None
    try:
        blocking = import_module("jeepney.io.blocking")
        jeepney = import_module("jeepney")
        open_connection = getattr(blocking, "open_dbus_connection")
        connection = cast(_DbusConnection, open_connection(bus="SESSION"))
        message_bus = cast(_MessageBus, getattr(jeepney, "message_bus"))
        name = f"ai.artificialsweetener.Substitute.Instance.i{identity}"
        reply = connection.send_and_get_reply(
            message_bus.RequestName(name, _DO_NOT_QUEUE)
        )
    except Exception:
        if connection is not None:
            connection.close()
        _LOGGER.info(
            "Linux session D-Bus is unavailable; using abstract socket election",
            exc_info=True,
        )
        return LinuxSessionBusResult(LinuxSessionBusElection.UNAVAILABLE)
    result = reply.body[0] if reply.body else None
    if result in {_PRIMARY_OWNER, _ALREADY_OWNER}:
        return LinuxSessionBusResult(
            LinuxSessionBusElection.PRIMARY,
            LinuxSessionBusClaim(connection, message_bus, name),
        )
    connection.close()
    return LinuxSessionBusResult(LinuxSessionBusElection.SECONDARY)


__all__ = [
    "LinuxSessionBusClaim",
    "LinuxSessionBusElection",
    "LinuxSessionBusResult",
    "acquire_linux_session_bus",
]
