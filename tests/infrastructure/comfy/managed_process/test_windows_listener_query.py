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

"""Qualify native Windows TCP-listener ownership resolution."""

from __future__ import annotations

import os
import socket
import subprocess

import pytest

from substitute.infrastructure.comfy.managed_process_query import (
    ListenerPidQueryStatus,
    query_listener_pid,
)


pytestmark = pytest.mark.platforms("windows")


def test_native_listener_query_resolves_owner_without_powershell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a live listener while making every subprocess fallback fatal."""

    def forbid_subprocess(*_args: object, **_kwargs: object) -> object:
        """Reject any process-based listener ownership query."""

        raise AssertionError("Listener ownership must not start a subprocess")

    monkeypatch.setattr(subprocess, "run", forbid_subprocess)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])

        result = query_listener_pid("127.0.0.1", port)

    assert result.status is ListenerPidQueryStatus.RESOLVED
    assert result.pid == os.getpid()
