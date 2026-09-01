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

from types import SimpleNamespace

import pytest

from sugarsubstitute_shared import application_instance_linux
from sugarsubstitute_shared.application_instance_linux import LinuxSessionBusElection


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
