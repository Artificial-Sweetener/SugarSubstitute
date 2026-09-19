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
from collections.abc import Mapping, Sequence

import pytest

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairScope,
)
from launcher.sugarsubstitute_launcher.repair_handoff import (
    launch_prepared_repair_helper,
)
from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    directory_tree_sha256,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.windows_long_paths import operational_path, subprocess_path
from launcher.sugarsubstitute_launcher.repair_bundle import (
    stage_independent_repair_bundle,
)


@pytest.mark.parametrize("target_key", ["windows_x64", "linux_x64", "macos_arm64"])
def test_handoff_retains_complete_bundle_and_binds_live_caller(
    tmp_path: Path,
    target_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launched helper should not depend on any root the transaction replaces."""

    root = (tmp_path / "install").resolve()
    staging = root / ".repair" / "staging" / "1.2.3"
    app = staging / "app"
    launcher = staging / "launcher"
    app.mkdir(parents=True)
    target = launcher_bundle_target_for_key(target_key)
    for relative in target.required_file_relative_paths:
        path = launcher / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"verified-executable")
    support = launcher / target.support_relative_path
    support.mkdir(parents=True, exist_ok=True)
    (support / "runtime-library.bin").write_bytes(b"required-native-runtime")
    request = PreparedRepairRequest(
        install_root=root,
        scope=RepairScope.APPLICATION,
        version="1.2.3",
        channel="stable",
        target_key=target_key,
        staged_app_dir=app,
        staged_launcher_dir=launcher,
        staged_app_sha256="a" * 64,
        staged_launcher_sha256=directory_tree_sha256(launcher),
    )
    request_path = root / ".repair" / "prepared.json"
    request = request.with_helper_bundle(stage_independent_repair_bundle(request))
    request.save(request_path)
    commands: list[tuple[str, ...]] = []
    from sugarsubstitute_shared import qt_application_instance_control
    from sugarsubstitute_shared.process_identity import ProcessIdentity
    from sugarsubstitute_shared.supervisor_handoff import consume_supervisor_handoff

    supervisor = ProcessIdentity(pid=321, created_at=1234.5)
    monkeypatch.setattr(
        qt_application_instance_control,
        "active_application_supervisor_identity",
        lambda: supervisor,
    )
    inherited: list[dict[str, str]] = []

    def start(command: Sequence[str], *, environment: Mapping[str, str]) -> None:
        """Capture process boundaries without starting a synthetic executable."""
        commands.append(tuple(command))
        inherited.append(dict(environment))

    helper = launch_prepared_repair_helper(
        request_path=request_path,
        starter=start,
        current_pid=os.getpid(),
    )

    persisted = PreparedRepairRequest.load(request_path)
    assert helper.read_bytes() == b"verified-executable"
    assert helper.is_relative_to(operational_path(root / ".repair" / "helper"))
    assert persisted.wait_pid == os.getpid()
    assert persisted.wait_process_created_at is not None
    assert consume_supervisor_handoff(inherited[0]) == supervisor
    assert commands == [
        (
            subprocess_path(helper),
            f"--execute-repair-request={subprocess_path(request_path)}",
        ),
    ]
    helper_bundle = helper
    for _part in target.executable_relative_path.parts:
        helper_bundle = helper_bundle.parent
    launcher.replace(staging / "promoted-launcher")
    assert (
        helper_bundle / target.support_relative_path / "runtime-library.bin"
    ).read_bytes() == b"required-native-runtime"
    for relative in target.required_file_relative_paths:
        assert (helper_bundle / relative).is_file()
