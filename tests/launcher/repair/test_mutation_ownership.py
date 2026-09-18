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

"""Preserve prepared update intent while repair owns installation mutation."""

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
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.transaction import LauncherUpdateTransaction
from .execution_support import (
    _RuntimeProvisioner,
    _prepared_request,
    _write_launcher,
    _write_old_install,
)


@pytest.mark.parametrize("rollback", [False, True])
def test_competing_update_retains_intent_until_repair_finishes(
    tmp_path: Path, rollback: bool
) -> None:
    """Defer a real competing updater until repair commit or rollback releases ownership."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)
    update = layout.launcher_dir / "updates" / "competing"
    _write_launcher(update)
    update_request = update.parent / "competing.json"
    LauncherUpdateRequest(
        install_root=layout.root,
        version="2.0.0",
        target_key=WINDOWS_X64_BUNDLE.key,
        staged_bundle_dir=update,
        relaunch=False,
    ).save(update_request)
    selection = LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE)
    selection_path = LauncherBundlePaths(layout.root).selection
    attempts: list[subprocess.CompletedProcess[str]] = []
    retained: list[bool] = []

    def interleave(_source: Path, destination: Path) -> None:
        """Attempt an actual update only after repair promotes its selection."""
        if destination.resolve() != selection_path.resolve():
            return
        attempts.append(
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "sugarsubstitute_shared.launcher_update.helper",
                    str(update_request),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
        )
        retained.append(update_request.exists())
        if rollback:
            raise RuntimeError("injected repair failure after competing update")

    service = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        transaction=RepairTransaction(after_move=interleave),
    )
    if rollback:
        with pytest.raises(RuntimeError, match="rolled back"):
            service.execute_application(request)
    else:
        service.execute_application(request)
    assert len(attempts) == 1
    assert retained == [True], attempts[0].stderr
    assert attempts[0].returncode != 0
    assert selection.resolve().version == (None if rollback else request.version)
    assert not (layout.root / ".repair" / "pending.json").exists()
    LauncherUpdateTransaction().apply(request_path=update_request)
    assert selection.resolve().version == "2.0.0"
    assert not update_request.exists()


def test_update_recovers_dead_repair_before_retiring_intent(tmp_path: Path) -> None:
    """Recover an interrupted transaction before an updater can supersede its selection."""
    from sugarsubstitute_shared.repair_recovery.execution import (
        recover_interrupted_repair,
    )

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    repair = _prepared_request(layout)
    repair.save(repair.request_path)
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.repair.selection_crash_process",
            str(repair.request_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    pending = layout.root / ".repair" / "pending.json"
    assert pending.exists()
    update = layout.launcher_dir / "updates" / "next"
    _write_launcher(update)
    request = update.parent / "next.json"
    LauncherUpdateRequest(
        install_root=layout.root,
        version="2.0.0",
        target_key=WINDOWS_X64_BUNDLE.key,
        staged_bundle_dir=update,
        relaunch=False,
    ).save(request)
    LauncherUpdateTransaction().apply(request_path=request)
    assert not pending.exists()
    assert not request.exists()
    assert layout.runtime_python.read_bytes() == b"old-python"
    assert "0.9.0" in (layout.app_dir / "substitute" / "_version.py").read_text()
    assert not recover_interrupted_repair(layout.root)
    assert (
        LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE).resolve().version
        == "2.0.0"
    )
