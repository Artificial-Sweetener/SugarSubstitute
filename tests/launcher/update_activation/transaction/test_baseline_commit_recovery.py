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

"""Safeguard committed baseline publication and stale backup ownership."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

import pytest

from sugarsubstitute_shared.launcher_update.baseline_transaction import (
    LauncherBaselineTransaction,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .support import _write_bundle_tree, _write_installed_layout
from .native_file_sharing import exclusive_read


def _request(root: Path) -> Path:
    """Persist one fully staged new baseline for the production transaction."""
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="new launcher")
    path = root / "launcher" / "updates" / "request.json"
    LauncherUpdateRequest(
        install_root=root,
        version="0.27.1",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(path)
    return path


def test_terminated_after_record_publication_retains_new_baseline(
    tmp_path: Path,
) -> None:
    """Real process termination after publication cannot restore incompatible old bytes."""
    root = _write_installed_layout(tmp_path / "installation")
    request = _request(root)
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.launcher.update_activation.transaction.baseline_boundary_child",
            str(request),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    ) as process:
        try:
            assert process.stdout is not None
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(process.stdout.readline)
                try:
                    boundary = future.result(timeout=30)
                finally:
                    process.kill()
                    output, errors = process.communicate(timeout=10)
            assert boundary.strip() == "installation-record-published", (output, errors)
            assert process.returncode != 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    LauncherBaselineTransaction().recover(install_root=root, target=WINDOWS_X64_BUNDLE)
    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "new launcher"
    assert LauncherInstallationRecord.load(
        root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.27.1", target_key="windows_x64")
    assert (root / "user" / "preserve.txt").read_text(encoding="utf-8") == "preserved"


@pytest.mark.platforms("windows")
def test_locked_stale_backup_never_becomes_current_baseline(tmp_path: Path) -> None:
    """An unremovable stale backup must block promotion without restoring stale content."""
    root = _write_installed_layout(tmp_path / "installation")
    request = _request(root)
    backup = root / "launcher" / "updates" / "backup"
    _write_bundle_tree(backup, marker="incompatible stale launcher")
    with exclusive_read(backup / "SugarSubstitute.exe"):
        with pytest.raises(OSError):
            LauncherBaselineTransaction(wait_timeout_seconds=0).apply(
                request_path=request
            )
    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "old launcher"
    assert not (root / "launcher" / "updates" / "transaction.json").exists()
