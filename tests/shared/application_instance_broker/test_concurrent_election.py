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

"""Prove exclusive native election across simultaneous independent processes."""

from contextlib import ExitStack
from pathlib import Path
import socket
import sys

import pytest

from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("contenders", [2, 4])
def test_simultaneous_launches_elect_one_owner_and_release_endpoint(
    tmp_path: Path, contenders: int
) -> None:
    """Cross a process barrier together and leave no stale native ownership."""
    processes: list[ChildProcess] = []
    streams: list[socket.SocketIO] = []
    with ExitStack() as resources:
        listener = resources.enter_context(socket.socket())
        listener.bind(("127.0.0.1", 0))
        listener.listen(contenders)
        listener.settimeout(20)
        try:
            for index in range(contenders):
                process, _log = spawn_supervised_process(
                    [
                        sys.executable,
                        "-m",
                        "tests.shared.application_instance_broker.election_contender",
                        str(tmp_path),
                        str(listener.getsockname()[1]),
                    ],
                    startup_log_path=tmp_path / f"contender-{index}.log",
                )
                processes.append(process)
            for _index in range(contenders):
                connection, _address = listener.accept()
                resources.enter_context(connection)
                connection.settimeout(20)
                stream = resources.enter_context(
                    connection.makefile("rwb", buffering=0)
                )
                assert stream.readline() == b"ready\n"
                streams.append(stream)
            for stream in streams:
                stream.write(b"go\n")
            outcomes = [stream.readline() for stream in streams]
            assert outcomes.count(b"owner\n") == 1
            assert outcomes.count(b"forwarded\n") == contenders - 1
            for stream in streams:
                stream.write(b"exit\n")
            for process in processes:
                assert process.wait(timeout=10) == 0
            replacement = ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(("replacement",)),
            )
            assert replacement is not None
            replacement.close()
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
