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

"""Exercise orphaned repair-caller recovery through real Windows process control."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import json
import os
from pathlib import Path
import socket
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher import (
    launcher_ui_supervision,
    repair_session_supervisor,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
    wait_for_process_exit,
)
from sugarsubstitute_shared.supervisor_handoff import with_supervisor_handoff

pytestmark = pytest.mark.platforms("windows")


class FixtureLayout(InstallLayout):
    """Use the repository runtime while preserving production caller-role checks."""

    @property
    def runtime_python(self) -> Path:
        """Locate the virtual-environment process launcher used by this fixture."""
        return Path(sys.executable)

    @property
    def runtime_gui_python(self) -> Path:
        """Include the virtual environment's actual Python payload executable."""
        return Path(getattr(sys, "_base_executable", sys.executable))


@pytest.mark.parametrize("retired_supervisor", [False, True])
def test_frozen_caller_without_live_supervisor_recovers_before_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retired_supervisor: bool
) -> None:
    """End the exact frozen caller through recovery and acquire repair ownership afterward."""
    layout = FixtureLayout.from_root(tmp_path / "installation")
    layout.app_dir.mkdir(parents=True)
    layout.app_entrypoint.write_text(
        "import json, os, socket, sys; from threading import Event\n"
        "with socket.create_connection(('127.0.0.1', int(sys.argv[-1])), timeout=5) as peer:\n"
        "    peer.sendall(json.dumps({'pid': os.getpid()}).encode())\n"
        "Event().wait(30)\n",
        encoding="utf-8",
    )
    offers: list[bool] = []
    presented: list[bool] = []
    current = capture_process_identity(os.getpid())
    environment = (
        with_supervisor_handoff(
            {}, ProcessIdentity(current.pid, current.created_at - 100)
        )
        if retired_supervisor
        else {}
    )
    monkeypatch.setattr(repair_session_supervisor, "InstallLayout", FixtureLayout)

    def recover(**kwargs: object) -> InstanceRecoveryAction:
        """Fail if retiring the real frozen caller requires manual intervention."""
        pytest.fail("Frozen caller required a user-operated recovery workflow")

    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", recover
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        process, _log = spawn_supervised_process(
            [
                sys.executable,
                str(layout.app_entrypoint),
                f"--install-root={layout.root}",
                str(listener.getsockname()[1]),
            ],
            startup_log_path=tmp_path / "caller.log",
        )
        try:
            root = psutil.Process(process.pid)
            connection, _address = listener.accept()
            with connection, connection.makefile("rb") as stream:
                connection.settimeout(5)
                caller_pid = int(json.loads(stream.read())["pid"])
            family = [root, *root.children(recursive=True)]
            identities = {member.pid: member for member in family}
            assert caller_pid in identities
            caller = identities[caller_pid]
            identity = capture_process_identity(caller_pid)
            caller.suspend()
            staging = layout.root / ".repair/staging/1.2.3"
            request = PreparedRepairRequest(
                layout.root,
                RepairScope.APPLICATION,
                "1.2.3",
                "stable",
                "windows_x64",
                staging / "app",
                staging / "launcher",
                "a" * 64,
                "b" * 64,
                wait_pid=identity.pid,
                wait_process_created_at=identity.created_at,
            )

            class Presentation:
                """Assert caller retirement before any repair work is allowed."""

                def run(
                    self,
                    candidate: PreparedRepairRequest,
                    environment: Mapping[str, str],
                ) -> int:
                    """Observe the real process state at repair presentation admission."""
                    assert candidate == request
                    assert not caller.is_running()
                    presented.append(True)
                    return 0

            assert (
                repair_session_supervisor.RepairSessionSupervisor(
                    presentation=Presentation(),
                    process_waiter=partial(wait_for_process_exit, timeout_seconds=0.05),
                    environment=environment,
                ).run(request)
                == 0
            )
            process.wait(timeout=5)
            _gone, alive = psutil.wait_procs(family, timeout=5)
            assert not alive
            assert offers == []
            assert presented == [True]
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
