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

"""Run bounded synthetic process families for native ownership qualification."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.process_execution import ChildProcess

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event


def main() -> None:
    """Publish each live descendant before blocking without cooperative cleanup."""
    role, raw_port, log_root = sys.argv[1:]
    port = int(raw_port)
    child: ChildProcess | None = None
    if role == "broker":
        from sugarsubstitute_shared.application_instance_broker import (
            ApplicationInstanceBroker,
        )
        from sugarsubstitute_shared.application_instance_protocol import (
            ApplicationInvocation,
        )

        broker = ApplicationInstanceBroker.elect(
            install_root=Path(log_root),
            invocation=ApplicationInvocation.capture(()),
        )
        assert broker is not None
        try:
            _publish_and_block(role, port)
        finally:
            broker.close()
        return
    if role == "handoff":
        from launcher.sugarsubstitute_launcher.process_execution import (
            spawn_detached_process,
        )

        child, _log = spawn_detached_process(
            command("leaf", port, Path(log_root)),
            startup_log_path=Path(log_root) / "handoff.log",
        )
    elif role == "owner":
        from launcher.sugarsubstitute_launcher.process_execution import (
            spawn_supervised_process,
        )

        child, _log = spawn_supervised_process(
            command("family", port, Path(log_root)),
            startup_log_path=Path(log_root) / "family.log",
        )
    elif role == "family":
        with subprocess.Popen(
            command("leaf", port, Path(log_root)),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ) as leaf:
            try:
                _publish_and_block(role, port)
            finally:
                leaf.kill()
                leaf.wait(timeout=5)
        return
    try:
        _publish_and_block(role, port)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def _publish_and_block(role: str, port: int) -> None:
    """Signal readiness before simulating a process with no responsive event loop."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall(json.dumps({"role": role, "pid": os.getpid()}).encode())
    Event().wait(60)


def command(role: str, port: int, log_root: Path) -> list[str]:
    """Keep every synthetic interpreter inside the repository virtual environment."""
    return [
        sys.executable,
        "-c",
        "from tests.launcher.application_readiness.process_family_fixture import main; main()",
        role,
        str(port),
        str(log_root),
    ]
