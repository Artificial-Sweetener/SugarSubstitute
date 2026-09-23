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

"""Qualify the two-step published update of a retained launcher root."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import launcher_baseline_refresh
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_baseline_refresh import (
    LauncherBaselineRefresh,
)
from sugarsubstitute_shared.launcher_update.attempt_status import (
    LauncherUpdateAttemptPhase,
    LauncherUpdateAttemptStore,
)
from sugarsubstitute_shared.launcher_update.baseline_refresh_helper import (
    apply_required_baseline_refresh,
)
from sugarsubstitute_shared.launcher_update.baseline_refresh_staging import (
    LauncherBaselineRefreshStager,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
    SelectedLauncherBundle,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update import process as update_process_module
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
)
from sugarsubstitute_shared.application_readiness import (
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
)
from sugarsubstitute_shared.process_identity import capture_process_identity

from .support import _write_bundle_tree, _write_installed_layout


def _write_delegation_contract(bundle_root: Path) -> None:
    """Give one synthetic bundle the published delegation contract."""

    contract = (
        bundle_root / "launcher-bin" / "launcher_assets" / "launcher-contract.json"
    )
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        json.dumps({"schema_version": 1, "delegation_protocol": 1}),
        encoding="utf-8",
    )


def _update_to_selected_generation(root: Path) -> SelectedLauncherBundle:
    """Exercise the existing normal update route from a 0.23.1 root."""

    _write_delegation_contract(root)
    LauncherInstallationRecord(version="0.23.1", target_key="windows_x64").save(
        root / "launcher" / "installation.json"
    )
    staged = root / "launcher" / "updates" / "candidate"
    _write_bundle_tree(staged, marker="0.24.2 selected launcher")
    _write_delegation_contract(staged)
    request_path = root / "launcher" / "updates" / "normal-update.json"
    LauncherUpdateRequest(
        install_root=root,
        version="0.24.2",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request_path)
    LauncherUpdateTransaction().apply(request_path=request_path)
    return LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve()


def test_normal_update_refreshes_retained_root_before_application_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A newer selected launcher must replace the old root through its own helper."""

    root = _write_installed_layout(tmp_path / "installation")
    selected = _update_to_selected_generation(root)
    assert selected.version == "0.24.2"
    assert LauncherInstallationRecord.load(
        root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.23.1", target_key="windows_x64")
    scheduled: list[tuple[Path, Path, int]] = []

    def schedule(*, request_path: Path, helper_executable: Path, wait_pid: int) -> int:
        """Capture the independent helper without launching a test desktop window."""

        scheduled.append((request_path, helper_executable, wait_pid))
        return 777

    monkeypatch.setattr(
        launcher_baseline_refresh, "schedule_required_baseline_refresh", schedule
    )
    image = selected.root / "SugarSubstitute.exe"

    assert LauncherBaselineRefresh().start_if_required(
        layout=InstallLayout.from_root(root), running_executable=image
    )
    assert len(scheduled) == 1
    request_path, helper_executable, _wait_pid = scheduled[0]
    assert helper_executable == image
    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "old launcher"

    apply_required_baseline_refresh(request_path)

    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == (
        "0.24.2 selected launcher"
    )
    assert LauncherInstallationRecord.load(
        root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.24.2", target_key="windows_x64")
    assert (root / "user" / "preserve.txt").read_text(encoding="utf-8") == "preserved"
    assert (root / "appdata" / "preserve.txt").read_text(encoding="utf-8") == (
        "preserved"
    )
    status = LauncherUpdateAttemptStore(root).load()
    assert status is not None
    assert status.phase is LauncherUpdateAttemptPhase.COMPLETED
    assert status.route == "required_baseline_refresh"
    assert not LauncherBaselineRefresh().start_if_required(
        layout=InstallLayout.from_root(root), running_executable=image
    )


def test_baseline_refresh_rejects_modified_staging_without_replacing_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A changed staged copy must not become the installation's root launcher."""

    root = _write_installed_layout(tmp_path / "installation")
    selected = _update_to_selected_generation(root)
    requests: list[Path] = []

    def schedule(*, request_path: Path, helper_executable: Path, wait_pid: int) -> int:
        """Capture the staged request before an independent process would start."""

        del helper_executable, wait_pid
        requests.append(request_path)
        return 777

    monkeypatch.setattr(
        launcher_baseline_refresh, "schedule_required_baseline_refresh", schedule
    )
    LauncherBaselineRefresh().start_if_required(
        layout=InstallLayout.from_root(root),
        running_executable=selected.root / "SugarSubstitute.exe",
    )
    request = LauncherUpdateRequest.load(requests[0])
    (request.staged_bundle_dir / "SugarSubstitute.exe").write_text(
        "modified candidate", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Staged baseline"):
        apply_required_baseline_refresh(requests[0])

    assert (root / "SugarSubstitute.exe").read_text(encoding="utf-8") == "old launcher"
    status = LauncherUpdateAttemptStore(root).load()
    assert status is not None
    assert status.phase is LauncherUpdateAttemptPhase.FAILED


def test_refresh_helper_runs_from_selected_generation_with_clean_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Never ask the installed root to replace its own running executable."""

    root = _write_installed_layout(tmp_path / "installation")
    selected = _update_to_selected_generation(root)
    request_path = LauncherBaselineRefreshStager().stage(
        install_root=root, selected=selected, target=WINDOWS_X64_BUNDLE
    )
    image = selected.root / "SugarSubstitute.exe"
    monkeypatch.setenv(READINESS_PATH_ENV, str(tmp_path / "stale.json"))
    monkeypatch.setenv(READINESS_TOKEN_ENV, "stale-token")
    launched: list[tuple[list[str], dict[str, str]]] = []

    def start(
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        output_fd: int,
    ) -> int:
        """Capture the helper command and environment at the OS boundary."""

        del output_fd
        assert cwd == root
        launched.append((command, environment))
        return 777

    monkeypatch.setattr(update_process_module, "_start_independent", start)

    helper_pid = update_process_module.schedule_required_baseline_refresh(
        request_path=request_path,
        helper_executable=image,
        wait_pid=os.getpid(),
    )

    assert helper_pid == 777
    assert launched[0][0] == [
        str(image.resolve()),
        "--apply-launcher-baseline-refresh",
        str(request_path.resolve()),
    ]
    assert READINESS_PATH_ENV not in launched[0][1]
    assert READINESS_TOKEN_ENV not in launched[0][1]
    saved = LauncherUpdateRequest.load(request_path)
    assert saved.relaunch
    assert saved.wait_identity == capture_process_identity(os.getpid())

    with pytest.raises(ValueError, match="verified selected launcher"):
        update_process_module.schedule_required_baseline_refresh(
            request_path=request_path,
            helper_executable=root / "SugarSubstitute.exe",
            wait_pid=os.getpid(),
        )
