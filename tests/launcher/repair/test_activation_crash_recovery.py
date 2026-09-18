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

"""Prove production repair retry after a native process dies during activation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .execution_support import (
    _RuntimeProvisioner,
    _prepared_request,
    _write_old_install,
    _write_launcher,
)


@pytest.mark.parametrize("previous_generation", [False, True])
def test_helper_recovers_interrupted_selection_then_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    previous_generation: bool,
) -> None:
    """Recover old state before retry without manual journal edits or new downloads."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)
    request.save(request.request_path)
    selection = LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE)
    if previous_generation:
        prior = layout.launcher_dir / "updates" / "prior"
        _write_launcher(prior)
        selection.activate(selection.publish(prior, version="0.9.0"))
    previous = selection.resolve()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.repair.selection_crash_process",
            str(request.request_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert completed.returncode == 73, completed.stderr
    pending = layout.root / ".repair" / "pending.json"
    assert pending.exists()
    assert selection.resolve().version == request.version
    version_path = layout.app_dir / "substitute" / "_version.py"
    recovery_observed: list[bool] = []

    def build_service(**_kwargs: object) -> RepairExecutionService:
        """Observe worker-owned recovery before providing the offline runtime boundary."""
        assert version_path.read_text(encoding="utf-8") == '__version__ = "0.9.0"\n'
        assert selection.resolve() == previous
        assert not pending.exists()
        recovery_observed.append(True)
        return RepairExecutionService(runtime_provisioner=_RuntimeProvisioner())

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.repair_helper.build_repair_execution_service",
        build_service,
    )
    result = run_prepared_repair(request.request_path)
    assert recovery_observed == [True]
    assert result.version == request.version
    assert selection.resolve().version == request.version
    assert layout.executable_path.read_bytes() == b"old-launcher"
    assert not pending.exists()
    assert not request.request_path.exists()
