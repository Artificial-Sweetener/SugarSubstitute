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

"""Require self-update to preserve the independently runnable installed entrypoint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.transaction import LauncherUpdateTransaction

from .support import _write_bundle_tree, _write_installed_layout


def _prepare_update(tmp_path: Path) -> tuple[Path, Path, dict[Path, str]]:
    """Prepare synthetic payloads and hash the complete durable baseline."""
    root = _write_installed_layout(tmp_path / "installation")
    baseline = {
        path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="candidate")
    request = root / "launcher" / "updates" / "pending.json"
    LauncherUpdateRequest(
        install_root=root,
        version="9999.0.1",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request)
    return root, request, baseline


def _assert_baseline(root: Path, expected: dict[Path, str]) -> None:
    """Require every baseline executable, dependency and user file to remain intact."""
    missing = [
        str(relative) for relative in expected if not (root / relative).is_file()
    ]
    assert not missing, f"Self-update removed durable entrypoint files: {missing}"
    changed = [
        str(relative)
        for relative, digest in expected.items()
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest
    ]
    assert not changed, f"Self-update replaced its durable baseline: {changed}"


def test_interrupted_publication_preserves_the_complete_entrypoint(
    tmp_path: Path,
) -> None:
    """Leave a runnable baseline after actual updater death, without helper retry."""
    root, request, baseline = _prepare_update(tmp_path)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[4])
    process, log_path = spawn_supervised_process(
        (
            sys.executable,
            "-m",
            "tests.launcher.update_activation.transaction.interruption_process",
            str(request),
            f"--install-root={root}",
        ),
        environment=environment,
    )
    try:
        return_code = process.wait(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    assert return_code == 73, log_path.read_text(encoding="utf-8")
    _assert_baseline(root, baseline)


def test_successful_publication_preserves_the_complete_entrypoint(
    tmp_path: Path,
) -> None:
    """Publish a candidate without consuming the recovery bootstrap's own files."""
    root, request, baseline = _prepare_update(tmp_path)
    LauncherUpdateTransaction().apply(request_path=request)
    _assert_baseline(root, baseline)
    selected = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve()
    assert selected.version == "9999.0.1"
    assert selected.root != root
    assert (selected.root / "SugarSubstitute.exe").read_text() == "candidate"


def test_update_recovers_older_replacement_journal_before_activation(
    tmp_path: Path,
) -> None:
    """Restore a baseline interrupted by the previous updater before selecting new code."""
    root, request, baseline = _prepare_update(tmp_path)
    updates = root / "launcher" / "updates"
    backup = updates / "backup"
    backup.mkdir()
    (root / "SugarSubstitute.exe").replace(backup / "SugarSubstitute.exe")
    (root / "launcher-bin").replace(backup / "launcher-bin")
    (updates / "transaction.json").write_text(
        json.dumps({"phase": "promoting", "target_key": "windows_x64"}),
        encoding="utf-8",
    )
    LauncherUpdateTransaction().apply(request_path=request)
    _assert_baseline(root, baseline)
    assert (
        LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve().version
        == "9999.0.1"
    )
    assert not (updates / "transaction.json").exists()


def test_failed_update_keeps_previous_selection_and_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the working generation selected when the next copy cannot complete."""
    root, request, baseline = _prepare_update(tmp_path)
    transaction = LauncherUpdateTransaction()
    transaction.apply(request_path=request)
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    previous = selection.resolve()
    LauncherUpdateRequest(
        install_root=root,
        version="9999.0.2",
        target_key="windows_x64",
        staged_bundle_dir=root / "launcher" / "updates" / "staged",
        relaunch=False,
    ).save(request)

    def fail_copy(*args: object, **kwargs: object) -> str:
        """Model an unavailable filesystem at the candidate-copy boundary."""
        raise PermissionError("candidate copy unavailable")

    monkeypatch.setattr(shutil, "copytree", fail_copy)
    with pytest.raises(PermissionError):
        transaction.apply(request_path=request)
    assert selection.resolve() == previous
    assert request.exists()
    _assert_baseline(root, baseline)
