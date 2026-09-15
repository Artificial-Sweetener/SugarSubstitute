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

"""Verify prepared execution retires the authoritative request after commit."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.execution_result import (
    CompletedRepair,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairScope,
)
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair


def test_helper_executes_and_retires_request_under_existing_ownership(
    tmp_path: Path,
) -> None:
    """Lifecycle metadata cannot make the execution owner wait or launch processes."""

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

    def execute(candidate: PreparedRepairRequest) -> CompletedRepair:
        """Return one committed outcome at the execution boundary."""

        assert candidate == request
        assert events == []
        events.append("executed")
        return CompletedRepair("1.2.3", root / ".repair" / "quarantine" / "tx", False)

    result = run_prepared_repair(
        request_path,
        executor=execute,
    )

    assert result.version == "1.2.3"
    assert events == ["executed"]
    assert not request_path.exists()
