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

"""Verify Linux session-bus election fallback behavior."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest

from sugarsubstitute_shared import application_instance_linux
from sugarsubstitute_shared.application_instance_linux import (
    LinuxSessionBusClaim,
    LinuxSessionBusElection,
    _DbusConnection,
    _DbusReply,
)


@dataclass(frozen=True, slots=True)
class _ElectionReply:
    """Return one deterministic D-Bus reply body."""

    body: tuple[object, ...]


class _ElectionConnection:
    """Record synchronous D-Bus ownership requests and disconnects."""

    def __init__(self) -> None:
        """Prepare one open fake connection."""

        self.requests: list[object] = []
        self.closed = False

    def send_and_get_reply(self, message: object) -> _DbusReply:
        """Record one request and return a successful reply."""

        self.requests.append(message)
        return cast(_DbusReply, _ElectionReply(body=(1,)))

    def close(self) -> None:
        """Record the connection close."""

        self.closed = True


class _ElectionMessageBus:
    """Build inspectable fake D-Bus ownership messages."""

    def RequestName(self, name: str, flags: int = 0) -> object:
        """Build one request-name marker."""

        return ("request", name, flags)

    def ReleaseName(self, name: str) -> object:
        """Build one release-name marker."""

        return ("release", name)


def test_missing_session_bus_environment_selects_socket_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use abstract-socket election when Jeepney cannot locate a session bus."""

    def open_without_session_bus(*, bus: str) -> object:
        """Model Jeepney's missing DBUS_SESSION_BUS_ADDRESS result."""

        assert bus == "SESSION"
        raise KeyError("DBUS_SESSION_BUS_ADDRESS")

    blocking = SimpleNamespace(open_dbus_connection=open_without_session_bus)
    monkeypatch.setattr(
        application_instance_linux,
        "import_module",
        lambda name: blocking if name == "jeepney.io.blocking" else SimpleNamespace(),
    )

    result = application_instance_linux.acquire_linux_session_bus("instance")

    assert result.election is LinuxSessionBusElection.UNAVAILABLE
    assert result.claim is None


def test_session_bus_claim_releases_name_before_disconnect() -> None:
    """Wait for D-Bus name release so immediate re-election cannot lose a race."""

    connection = _ElectionConnection()
    message_bus = _ElectionMessageBus()
    claim = LinuxSessionBusClaim(
        cast(_DbusConnection, connection),
        message_bus,
        "ai.artificialsweetener.Substitute.Instance.example",
    )

    claim.close()
    claim.close()

    assert connection.requests == [
        ("release", "ai.artificialsweetener.Substitute.Instance.example")
    ]
    assert connection.closed
