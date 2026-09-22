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

"""Retire older payload recovery intent before a new repair becomes authoritative."""

from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import pytest
from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupCandidate
from launcher.sugarsubstitute_launcher.startup_recovery import recover_startup_candidate
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    update_journal_path,
)
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair
from .execution_support import (
    _RuntimeProvisioner,
    _prepared_request,
    _write_old_install,
)


@pytest.mark.parametrize("runtime_existed", [False, True])
@pytest.mark.parametrize("helper_entry", [False, True])
def test_repair_retires_prior_payload_update_before_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_existed: bool,
    helper_entry: bool,
) -> None:
    """Keep successful repair intact when the next ordinary startup checks old journals."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    if not runtime_existed:
        source = layout.runtime_dir.resolve()
        destination = (layout.root / "fixture-original-runtime").resolve()
        assert source.is_relative_to(tmp_path.resolve()) and destination.is_relative_to(
            tmp_path.resolve()
        )
        source.replace(destination)
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.update_activation.ownership_process",
            str(layout.root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    journal = update_journal_path(layout)
    assert journal.exists()
    request = _prepared_request(layout)
    request.save(request.request_path)
    service = RepairExecutionService(runtime_provisioner=_RuntimeProvisioner())
    if helper_entry:
        monkeypatch.setattr(
            "launcher.sugarsubstitute_launcher.repair_helper.build_repair_execution_service",
            lambda **_kwargs: service,
        )
        result = run_prepared_repair(request.request_path)
        assert result.version == request.version
    else:
        service.execute_application(request)
    assert not journal.exists()
    assert layout.runtime_python.read_bytes() == b"candidate-python"
    recover_startup_candidate(LauncherStartupCandidate(layout, True))
    assert layout.runtime_python.read_bytes() == b"candidate-python"
