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

"""Prove native cleanup of uncooperative children without killing unrelated apps."""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
import socket

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    stop_candidate_process,
)
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from tests.launcher.application_readiness.process_family_fixture import command
from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize(
    "failure",
    [
        "candidate_stop",
        "supervisor_death",
        "root_exit",
        "handoff",
        "contained_handoff",
        "wide_family",
    ],
)
def test_supervised_family_cannot_outlive_its_owner(
    tmp_path: Path, failure: str
) -> None:
    """Kill only a verified fixture owner and require all its descendants to exit."""
    root = None
    retained_owner: psutil.Process | None = None
    family: list[psutil.Process] = []
    with socket.socket() as listener, ExitStack() as process_handles:
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        listener.settimeout(10)
        port = listener.getsockname()[1]
        role = {
            "supervisor_death": "owner",
            "handoff": "handoff",
            "contained_handoff": "handoff",
            "wide_family": "wide_family",
        }.get(failure, "family")
        try:
            root, _log = spawn_supervised_process(
                command(role, port, tmp_path),
                startup_log_path=tmp_path / "owner.log",
                allow_handoff=failure == "handoff",
            )
            retained_owner = psutil.Process(root.pid)
            records: dict[str, int] = {}
            expected_records = {"owner": 3, "wide_family": 21}.get(role, 2)
            for _ in range(expected_records):
                connection, _address = listener.accept()
                with connection:
                    connection.settimeout(5)
                    with connection.makefile("rb") as response:
                        record = json.loads(response.read())
                records[record["role"]] = record["pid"]
            assert len(records) == expected_records
            root_identity = retained_owner
            family = [root_identity, *root_identity.children(recursive=True)]
            identities = {process.pid: process for process in family}
            assert set(records.values()).issubset(identities)
            native = NativeProcessHandleApi()
            retained: dict[int, int] = {}
            for member in family:
                handle = native.open(member.pid)
                assert handle is not None
                process_handles.callback(native.close, handle)
                assert (
                    abs(native.creation_time(handle) - member.create_time()) < 0.000_001
                )
                retained[member.pid] = handle
            survivors: set[int] = set()
            if failure == "handoff":
                handoff_root = identities[records["leaf"]]
                while handoff_root.ppid() != records["handoff"]:
                    handoff_root = identities[handoff_root.ppid()]
                survivors = {
                    handoff_root.pid,
                    *(child.pid for child in handoff_root.children(recursive=True)),
                }

            if failure == "supervisor_death":
                owner = identities[records["owner"]]
                owner.kill()
                owner.wait(timeout=5)
            elif failure == "root_exit":
                identities[records["family"]].kill()
                root.wait(timeout=5)
            else:
                stop_candidate_process(root)

            expected_stopped = family
            if failure == "handoff":
                leaf = identities[records["leaf"]]
                assert leaf.is_running(), (
                    "An intentional handoff was killed with its previous owner"
                )
                expected_stopped = [
                    process for process in family if process.pid not in survivors
                ]
            if failure != "supervisor_death":
                assert all(
                    native.wait(retained[process.pid], 0)
                    for process in expected_stopped
                ), "Supervision reported completion before native descendant exit"
            _gone, alive = psutil.wait_procs(expected_stopped, timeout=5)
            assert not alive, (
                "Supervision left live processes requiring manual cleanup: "
                f"{[(process.pid, process.name()) for process in alive]}"
            )
        finally:
            if retained_owner is not None and retained_owner.is_running():
                try:
                    family.extend(retained_owner.children(recursive=True))
                    family.append(retained_owner)
                except psutil.NoSuchProcess:
                    pass
            for process in reversed(family):
                try:
                    if process.is_running():
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
            if family:
                _gone, remaining = psutil.wait_procs(family, timeout=5)
                assert not remaining, "Fixture cleanup left a live test process"
            if root is not None:
                root.wait(timeout=5)
