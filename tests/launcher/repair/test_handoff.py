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

"""Verify independent helper staging and caller-identity handoff."""

from __future__ import annotations

import os
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair import (
    PreparedRepairRequest,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.repair_handoff import (
    launch_prepared_repair_helper,
)


def test_handoff_copies_verified_repair_exe_and_binds_live_caller(
    tmp_path: Path,
) -> None:
    """The launched helper should not depend on any root the transaction replaces."""

    root = (tmp_path / "install").resolve()
    staging = root / ".repair" / "staging" / "1.2.3"
    app = staging / "app"
    launcher = staging / "launcher"
    app.mkdir(parents=True)
    (launcher / "launcher-bin").mkdir(parents=True)
    (launcher / "launcher-bin" / "Repair.exe").write_bytes(b"one-file-helper")
    request = PreparedRepairRequest(
        install_root=root,
        scope=RepairScope.APPLICATION,
        version="1.2.3",
        channel="stable",
        target_key="windows_x64",
        staged_app_dir=app,
        staged_launcher_dir=launcher,
        staged_app_sha256="a" * 64,
        staged_launcher_sha256="b" * 64,
    )
    request_path = root / ".repair" / "prepared.json"
    request.save(request_path)
    commands: list[tuple[str, ...]] = []

    helper = launch_prepared_repair_helper(
        request_path=request_path,
        starter=lambda command: commands.append(tuple(command)),
        current_pid=os.getpid(),
    )

    persisted = PreparedRepairRequest.load(request_path)
    assert helper.read_bytes() == b"one-file-helper"
    assert helper.is_relative_to(root / ".repair" / "helper")
    assert persisted.wait_pid == os.getpid()
    assert persisted.wait_process_created_at is not None
    assert commands == [
        (str(helper), f"--execute-repair-request={request_path}"),
    ]
