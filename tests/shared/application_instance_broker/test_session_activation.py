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

"""Reject inaccessible desktop activation without replacing the existing owner."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys

import pytest

from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
)
from sugarsubstitute_shared.process_identity import capture_process_identity
from sugarsubstitute_shared import windows_process_security

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("session_observation", ["different", "unavailable"])
def test_inaccessible_session_retains_owner_and_allows_later_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, session_observation: str
) -> None:
    """Use native IPC with a real child and control only OS session observations."""
    invocation = ApplicationInvocation.capture(("fixture-document.sugar",))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(20)
        process, _log = spawn_supervised_process(
            [
                sys.executable,
                "-m",
                "tests.shared.application_instance_broker.election_contender",
                str(tmp_path),
                str(listener.getsockname()[1]),
            ],
            startup_log_path=tmp_path / "owner.log",
        )
        try:
            connection, _address = listener.accept()
            with connection:
                connection.settimeout(20)
                with connection.makefile("rwb", buffering=0) as stream:
                    assert stream.readline() == b"ready\n"
                    stream.write(b"go\n")
                    assert stream.readline() == b"owner\n"

                    def observe_session(pid: int) -> int:
                        """Model an inaccessible peer desktop without moving any window."""
                        if pid == os.getpid():
                            return 1
                        if session_observation == "unavailable":
                            raise OSError("fixture session identity unavailable")
                        return 2

                    with monkeypatch.context() as session_boundary:
                        session_boundary.setattr(
                            windows_process_security,
                            "process_session_id",
                            observe_session,
                        )
                        with pytest.raises(ApplicationInstanceBrokerError) as caught:
                            ApplicationInstanceBroker.elect(
                                install_root=tmp_path, invocation=invocation
                            )
                    identity = caught.value.owner_identity
                    assert caught.value.reason == (
                        "other-session"
                        if session_observation == "different"
                        else "session-unverified"
                    )
                    assert identity is not None
                    assert identity == capture_process_identity(identity.pid)
                    assert process.poll() is None
                    assert (
                        ApplicationInstanceBroker.elect(
                            install_root=tmp_path, invocation=invocation
                        )
                        is None
                    )
                    stream.write(b"exit\n")
            assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
