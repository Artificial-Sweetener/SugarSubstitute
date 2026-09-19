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

"""Qualify repair-to-application transition inside native process containment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
from ctypes import wintypes
import json
import os
import shutil
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import repair_session_supervisor
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("exit_code", [0, 7])
def test_completed_repair_opens_application_inside_containing_job(
    tmp_path: Path, exit_code: int
) -> None:
    """Complete repair without escaping containment and retain the application's outcome."""
    root = tmp_path / "installation"
    root.mkdir()
    shutil.copy2(sys.executable, root / "SugarSubstitute.exe")
    receipt = tmp_path / "transition.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd())
    process, log = spawn_supervised_process(
        (
            sys.executable,
            str(Path(__file__)),
            "repair",
            str(root),
            str(receipt),
            str(exit_code),
        ),
        environment=environment,
        startup_log_path=tmp_path / "transition.log",
    )
    try:
        assert process.wait(timeout=20) == exit_code, log.read_text(encoding="utf-8")
        result = json.loads(receipt.read_text(encoding="utf-8"))
        assert result["application_pid"] != process.pid
        assert result["arguments"] == [
            str(root / "SugarSubstitute.exe"),
            f"--install-root={root}",
        ]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


class CompletedPresentation:
    """Request ordinary application opening through the real repair broker."""

    def run(
        self, request: PreparedRepairRequest, environment: Mapping[str, str]
    ) -> int:
        """Finish repair with an authenticated open request."""
        client = ApplicationSupervisorClient.connect_from_environment(dict(environment))
        assert client is not None
        try:
            assert client.request_restart()
        finally:
            client.close()
        return 0


def run_transition(root: Path, receipt: Path, exit_code: int) -> int:
    """Exercise real ownership and Windows creation with a bounded application payload."""
    from sugarsubstitute_shared.windows_process_job_api import (
        ExtendedLimits,
        load_kernel,
    )

    kernel = load_kernel()
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    assert job
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000
    assert kernel.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    )
    assert kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())
    # The process owns this kill-on-close handle until exit; closing it kills itself.

    def start_application(
        command: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        startup_log_path: Path | None = None,
        allow_handoff: bool = False,
    ) -> tuple[ChildProcess, Path]:
        """Substitute only the packaged payload while retaining native process creation."""
        receipt.with_suffix(".command.json").write_text(
            json.dumps(list(command)), encoding="utf-8"
        )
        return spawn_supervised_process(
            (
                sys.executable,
                str(Path(__file__)),
                "application",
                str(root),
                str(receipt),
                str(exit_code),
            ),
            environment=environment,
            startup_log_path=receipt.with_suffix(".application.log"),
            allow_handoff=allow_handoff,
        )

    staging = root / ".repair/staging/1.2.3"
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
        relaunch=True,
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            repair_session_supervisor, "spawn_supervised_process", start_application
        )
        return repair_session_supervisor.RepairSessionSupervisor(
            presentation=CompletedPresentation()
        ).run(request)


def run_application(root: Path, receipt: Path, exit_code: int) -> int:
    """Require released repair ownership before the replacement admits application work."""
    broker = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(())
    )
    assert broker is not None
    with broker:
        arguments = json.loads(
            receipt.with_suffix(".command.json").read_text(encoding="utf-8")
        )
        receipt.write_text(
            json.dumps({"application_pid": os.getpid(), "arguments": arguments}),
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    run = run_transition if sys.argv[1] == "repair" else run_application
    raise SystemExit(run(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])))
