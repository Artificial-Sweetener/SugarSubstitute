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

"""Require launcher-created splash descendants to share their owner's lifetime."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.process_execution import spawn_detached_process

pytestmark = pytest.mark.platforms("windows")


def test_frozen_splash_family_cannot_survive_supervisor_death(tmp_path: Path) -> None:
    """A non-cooperative splash must not need a user to end its processes."""
    family: list[psutil.Process] = []
    root = None
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(3)
        listener.settimeout(10)
        port = listener.getsockname()[1]
        try:
            root, _log = spawn_detached_process(
                [
                    sys.executable,
                    "-c",
                    "from tests.launcher.application_readiness.splash_family_fixture import main; main()",
                    str(tmp_path),
                    str(port),
                ],
                startup_log_path=tmp_path / "owner.log",
            )
            records: dict[str, int] = {}
            for _ in range(3):
                connection, _address = listener.accept()
                with connection:
                    connection.settimeout(5)
                    with connection.makefile("rb") as stream:
                        record = json.loads(stream.read())
                records[record["role"]] = record["pid"]
            owner = psutil.Process(root.pid)
            family = [owner, *owner.children(recursive=True)]
            identities = {p.pid: p for p in family}
            assert set(records.values()).issubset(identities)
            identities[records["splash"]].suspend()
            identities[records["owner"]].kill()
            _gone, alive = psutil.wait_procs(family, timeout=5)
            assert not alive, f"Orphaned splash processes: {[p.pid for p in alive]}"
        finally:
            if root is not None:
                try:
                    owner = psutil.Process(root.pid)
                    family.extend([owner, *owner.children(recursive=True)])
                except psutil.NoSuchProcess:
                    pass
            for process in reversed(family):
                try:
                    if process.is_running():
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
            _gone, remaining = psutil.wait_procs(family, timeout=5)
            assert not remaining, "Fixture cleanup left a live process"
            if root is not None:
                root.wait(timeout=5)
