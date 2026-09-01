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

"""Verify prepared helper waiting, execution, cleanup, and relaunch."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair import (
    CompletedRepair,
    PreparedRepairRequest,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair
from launcher.sugarsubstitute_launcher.repair_process import RepairProcessIdentity


def test_helper_waits_for_exact_caller_then_executes_and_relaunches(
    tmp_path: Path,
) -> None:
    """Mutation must start after the identified caller exits and cleanup follows commit."""

    root = (tmp_path / "install").resolve()
    staging = root / ".repair" / "staging" / "1.2.3"
    request = PreparedRepairRequest(
        install_root=root,
        scope=RepairScope.APPLICATION,
        version="1.2.3",
        channel="stable",
        target_key="windows_x64",
        staged_app_dir=staging / "app",
        staged_launcher_dir=staging / "launcher",
        staged_app_sha256="a" * 64,
        staged_launcher_sha256="b" * 64,
        wait_pid=77,
        wait_process_created_at=123.5,
        relaunch=True,
    )
    request_path = root / ".repair" / "prepared.json"
    request.save(request_path)
    events: list[str] = []
    launches: list[tuple[str, ...]] = []

    def wait(identity: RepairProcessIdentity) -> None:
        """Record the identity used by the helper."""

        assert identity == RepairProcessIdentity(77, 123.5)
        events.append("waited")

    def execute(candidate: PreparedRepairRequest) -> CompletedRepair:
        """Prove execution follows waiting and return a committed outcome."""

        assert candidate == request
        assert events == ["waited"]
        events.append("executed")
        return CompletedRepair("1.2.3", root / ".repair" / "quarantine" / "tx", False)

    result = run_prepared_repair(
        request_path,
        executor=execute,
        process_waiter=wait,
        app_starter=lambda command: launches.append(command),
    )

    assert result.version == "1.2.3"
    assert events == ["waited", "executed"]
    assert not request_path.exists()
    assert launches == [
        (
            str(root / "runtime" / ".venv" / "Scripts" / "python.exe"),
            str(root / "app" / "main.py"),
            f"--install-root={root}",
        )
    ]
