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

"""Prove readiness qualification across legacy detached update handoffs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
)
from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)


class _CandidateProcess:
    """Expose one deterministic running candidate to the supervisor."""

    pid = 321

    def poll(self) -> int | None:
        """Report a running process."""

        return None

    def terminate(self) -> None:
        """Reject unexpected termination in this successful path."""

        raise AssertionError("successful readiness must not terminate the candidate")

    def kill(self) -> None:
        """Reject unexpected forced termination in this successful path."""

        raise AssertionError("successful readiness must not kill the candidate")

    def wait(self, timeout: float | None = None) -> int:
        """Reject an unexpected wait on the running candidate."""

        raise subprocess.TimeoutExpired("candidate", timeout or 0.0)


def _qualification_plan(
    layout: InstallLayout, tmp_path: Path
) -> InstallerQualificationPlan:
    """Build one explicit qualification plan for the installed root."""

    return InstallerQualificationPlan(
        token="qualification-token",
        install_root=layout.root,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=tmp_path / "qualification.jsonl",
        timeout_seconds=45.0,
    )


def test_supervisor_publishes_qualification_receipt_without_outer_contract(
    tmp_path: Path,
) -> None:
    """Legacy updater handoffs should retain proof after readiness env cleanup."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess()
    plan = _qualification_plan(layout, tmp_path)

    def start(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Publish through the launcher's private child readiness contract."""

        receipt_path = Path(environment[READINESS_PATH_ENV])
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(
                ApplicationReadinessReceipt(
                    pid=process.pid,
                    token=environment[READINESS_TOKEN_ENV],
                    surface=ApplicationReadinessSurface.MAIN_SHELL,
                    parent_pid=999,
                ).to_json()
            ),
            encoding="utf-8",
        )
        return process, tmp_path / "startup.log"

    result = ApplicationReadinessSupervisor(
        timeout_seconds=5,
        process_starter=start,
    ).launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment={INSTALLER_QUALIFICATION_PLAN_ENV: plan.to_json()},
    )
    mirrored = ApplicationReadinessReceipt.from_json(
        json.loads(plan.readiness_receipt_path.read_text(encoding="utf-8"))
    )

    assert result is process
    assert mirrored.pid == process.pid
    assert mirrored.token == plan.token
    assert mirrored.surface is ApplicationReadinessSurface.MAIN_SHELL
    assert os.getpid() in mirrored.attester_pids


@pytest.mark.platforms("windows")
def test_real_process_mirrors_readiness_after_legacy_update_handoff(
    tmp_path: Path,
) -> None:
    """Prove a real app child can satisfy CI without an outer readiness contract."""

    layout = InstallLayout.from_root(tmp_path / "install")
    plan = _qualification_plan(layout, tmp_path)
    script = (
        "import json, os, time; "
        "from pathlib import Path; "
        "from sugarsubstitute_shared.application_readiness import "
        "ApplicationReadinessReceipt, ApplicationReadinessSurface, "
        "READINESS_PATH_ENV, READINESS_TOKEN_ENV; "
        "path = Path(os.environ[READINESS_PATH_ENV]); "
        "path.parent.mkdir(parents=True, exist_ok=True); "
        "path.write_text(json.dumps(ApplicationReadinessReceipt("
        "pid=os.getpid(), parent_pid=os.getppid(), "
        "token=os.environ[READINESS_TOKEN_ENV], "
        "surface=ApplicationReadinessSurface.MAIN_SHELL).to_json()), "
        "encoding='utf-8'); "
        "time.sleep(2)"
    )

    process = ApplicationReadinessSupervisor(timeout_seconds=5).launch_until_ready(
        layout=layout,
        command=[sys.executable, "-c", script],
        environment={INSTALLER_QUALIFICATION_PLAN_ENV: plan.to_json()},
    )
    mirrored = ApplicationReadinessReceipt.from_json(
        json.loads(plan.readiness_receipt_path.read_text(encoding="utf-8"))
    )

    assert mirrored.token == plan.token
    assert mirrored.surface is ApplicationReadinessSurface.MAIN_SHELL
    assert process.pid in {
        mirrored.pid,
        mirrored.parent_pid,
        *mirrored.attester_pids,
    }
    assert process.wait(timeout=5) == 0
