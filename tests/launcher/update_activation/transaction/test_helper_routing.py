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

"""Verify durable routing between legacy baselines and launcher generations."""

from __future__ import annotations

import json
from pathlib import Path

from sugarsubstitute_shared.launcher_update.attempt_status import (
    LauncherUpdateAttemptPhase,
    LauncherUpdateAttemptStore,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.helper import (
    apply_launcher_update_request,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import _write_bundle_tree, _write_installed_layout


def _write_delegation_contract(bundle_root: Path) -> None:
    """Mark one synthetic bundle as a permanent delegating launcher."""

    contract = (
        bundle_root / "launcher-bin" / "launcher_assets" / "launcher-contract.json"
    )
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        json.dumps({"schema_version": 1, "delegation_protocol": 1}),
        encoding="utf-8",
    )


def _write_request(root: Path, staged: Path, *, version: str) -> Path:
    """Persist one launcher update request within its owned update tree."""

    request_path = root / "launcher" / "updates" / "pending.json"
    LauncherUpdateRequest(
        install_root=root,
        version=version,
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request_path)
    return request_path


def test_helper_bridges_non_delegating_baseline_once(tmp_path: Path) -> None:
    """Replace a legacy baseline while preserving application and user state."""

    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="permanent bootstrap")
    _write_delegation_contract(staged)
    request_path = _write_request(root, staged, version="0.23.0")

    apply_launcher_update_request(request_path)

    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == (
        "permanent bootstrap"
    )
    assert (root / "user" / "preserve.txt").read_text(encoding="utf-8") == ("preserved")
    assert (root / "appdata" / "preserve.txt").read_text(encoding="utf-8") == (
        "preserved"
    )
    assert LauncherInstallationRecord.load(
        root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.23.0", target_key="windows_x64")
    status = LauncherUpdateAttemptStore(root).load()
    assert status is not None
    assert status.phase is LauncherUpdateAttemptPhase.COMPLETED
    assert status.route == "legacy_baseline_bridge"


def test_helper_activates_generation_after_permanent_bootstrap(tmp_path: Path) -> None:
    """Keep the permanent baseline immutable after its one-time migration."""

    root = _write_installed_layout(tmp_path / "installation")
    _write_delegation_contract(root)
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="generation")
    _write_delegation_contract(staged)
    request_path = _write_request(root, staged, version="0.24.0")

    apply_launcher_update_request(request_path)

    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "old launcher"
    selected = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve()
    assert selected.version == "0.24.0"
    assert (selected.root / "SugarSubstitute.exe").read_text(encoding="utf-8") == (
        "generation"
    )
    status = LauncherUpdateAttemptStore(root).load()
    assert status is not None
    assert status.phase is LauncherUpdateAttemptPhase.COMPLETED
    assert status.route == "generation_activation"


def test_helper_persists_terminal_failure_without_mutating_legacy_baseline(
    tmp_path: Path,
) -> None:
    """Expose an incompatible bridge immediately and preserve the old launcher."""

    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="non-delegating candidate")
    request_path = _write_request(root, staged, version="0.23.0")

    try:
        apply_launcher_update_request(request_path)
    except ValueError as error:
        assert "permanent delegation" in str(error)
    else:
        raise AssertionError("Expected the unsafe legacy bridge to fail.")

    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "old launcher"
    status = LauncherUpdateAttemptStore(root).load()
    assert status is not None
    assert status.phase is LauncherUpdateAttemptPhase.FAILED
    assert status.error_type == "ValueError"
