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

"""Exercise recovery while the real Windows endpoint owner cannot run any thread."""

from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import socket

import psutil  # type: ignore[import-untyped]
import pytest
from sugarsubstitute_shared.process_identity import capture_process_identity

from launcher.sugarsubstitute_launcher.application_instance_recovery import (
    terminate_verified_process,
)
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_instance_transport import (
    connect_instance_endpoint,
    instance_endpoint,
    instance_identity,
)
from tests.launcher.application_readiness.process_family_fixture import command

pytestmark = pytest.mark.platforms("windows")


def test_recovery_remains_available_when_owner_cannot_accept_more_connections(
    tmp_path: Path,
) -> None:
    """Recover an authenticated owner even after its frozen accept queue fills."""
    with socket.socket() as listener, ExitStack() as connections:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        root, _log = spawn_supervised_process(
            command("broker", listener.getsockname()[1], tmp_path),
            startup_log_path=tmp_path / "broker.log",
        )
        try:
            connection, _address = listener.accept()
            with connection, connection.makefile("rb") as response:
                connection.settimeout(5)
                owner_pid = int(json.loads(response.read())["pid"])
            root_identity = psutil.Process(root.pid)
            descendants = {
                child.pid: child for child in root_identity.children(recursive=True)
            }
            descendants[root.pid] = root_identity
            assert owner_pid in descendants
            owner = descendants[owner_pid]
            executable = Path(owner.exe())
            owner.suspend()
            endpoint = instance_endpoint(instance_identity(tmp_path))
            authenticated_owner = None
            verified_identity = None
            for _ in range(4):
                try:
                    peer = connect_instance_endpoint(endpoint)
                except OSError:
                    break
                connections.callback(peer.close)
                authenticated_owner = peer.peer_process_id()
                assert authenticated_owner == owner_pid
                verified_identity = capture_process_identity(authenticated_owner)
            else:
                pytest.fail("The frozen owner unexpectedly accepted an unbounded queue")
            assert authenticated_owner == owner_pid
            assert verified_identity is not None
            assert terminate_verified_process(
                verified_identity,
                expected_executable=executable,
            ), "Recovery required cooperation from the hung owner"
            root.wait(timeout=5)
        finally:
            root.kill()
            root.wait(timeout=5)
