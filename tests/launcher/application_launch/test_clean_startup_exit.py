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

"""Prove startup disposition using real children and authenticated exit receipts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_lifecycle_supervisor import (
    ApplicationLifecycleSupervisor,
)
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore


@pytest.mark.parametrize(
    "receipt,exit_code", [("complete", 0), ("none", 0), ("intent", 0), ("complete", 1)]
)
def test_pre_readiness_exit_preserves_authoritative_crash_disposition(
    tmp_path: Path, receipt: str, exit_code: int
) -> None:
    """A proven clean startup close ends normally; incomplete or failed exits do not."""
    layout = InstallLayout.from_root(tmp_path / "install")
    children: list[ChildProcess] = []
    reports: list[str] = []
    ready: list[bool] = []

    def start_process(
        command: Sequence[str], environment: Mapping[str, str]
    ) -> tuple[ChildProcess, Path]:
        """Exercise the real process boundary while retaining cleanup ownership."""
        process, log_path = spawn_supervised_process(
            command, environment=environment, startup_log_path=tmp_path / "child.log"
        )
        children.append(process)
        return process, log_path

    script = (
        "import os,sys; "
        "from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext,CleanExitOutcome; "
        "c=CrashRunContext.from_environment(); assert c is not None; "
    )
    if receipt != "none":
        script += (
            "c.write_exit_intent(CleanExitOutcome.CLOSED, process_id=os.getpid()); "
        )
    if receipt == "complete":
        script += (
            "c.write_exit_receipt(CleanExitOutcome.CLOSED, process_id=os.getpid()); "
        )
    script += f"sys.exit({exit_code})"
    crash = ApplicationCrashSupervisor(
        reporter_starter=lambda _layout, incident, _env: reports.append(incident),
    )
    lifecycle = ApplicationLifecycleSupervisor(
        process_starter=start_process,
        crash_supervisor=crash,
        readiness_timeout_seconds=10,
    )
    try:
        if receipt == "complete" and exit_code == 0:
            assert (
                lifecycle.supervise(
                    layout=layout,
                    command=(sys.executable, "-c", script),
                    environment=os.environ,
                    on_ready=lambda: ready.append(True),
                )
                == 0
            )
            assert (
                CrashIncidentStore(layout.appdata_dir / "diagnostics/crashes").pending()
                == ()
            )
        else:
            with pytest.raises(ApplicationReadinessError) as failure:
                lifecycle.supervise(
                    layout=layout,
                    command=(sys.executable, "-c", script),
                    environment=os.environ,
                    on_ready=lambda: ready.append(True),
                )
            incidents = CrashIncidentStore(
                layout.appdata_dir / "diagnostics/crashes"
            ).pending()
            assert len(incidents) == 1
            assert failure.value.incident_id == incidents[0].incident_id
        assert ready == []
        assert reports == []
        assert children and all(child.poll() is not None for child in children)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
