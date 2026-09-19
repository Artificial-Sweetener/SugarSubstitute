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

"""Verify measured transfer progress through real repair artifact preparation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparationService,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.repair_preparation_operation import (
    RepairPreparationOperation,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessCancelled,
    RepairProcessError,
)


def _create_release(tmp_path: Path) -> LocalFolderReleaseSource:
    """Build reusable synthetic archives and a real local provider manifest."""
    members = (
        (
            "main.py",
            "requirements.txt",
            "sitecustomize.py",
            "substitute/__init__.py",
            "third_party/NOTICE.md",
        ),
        (
            "SugarSubstitute.exe",
            "launcher-bin/LauncherUi.exe",
            "launcher-bin/Repair.exe",
            "launcher-bin/runtime.txt",
        ),
    )
    assets: list[dict[str, object]] = []
    for index, names in enumerate(members):
        path = tmp_path / f"archive-{index}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, b"synthetic release fixture")
            fixture_root = "substitute" if index == 0 else "launcher-bin"
            archive.writestr(
                f"{fixture_root}/transfer-fixture.bin", b"0" * (2 * 1024 * 1024)
            )
        assets.append(
            {
                "filename": path.name,
                "url": path.as_uri(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "channel": "stable",
                "version": "1.2.3",
                "minimum_launcher_version": "1.0.0",
                "app": assets[0],
                "launchers": {WINDOWS_X64.key: assets[1]},
                "installers": {},
            }
        ),
        encoding="utf-8",
    )
    return LocalFolderReleaseSource(tmp_path)


def test_real_preparation_reports_transfer_before_staging_is_complete(
    tmp_path: Path,
) -> None:
    """Deliver measured events from both composed downloaders and retain readiness ordering."""
    source = _create_release(tmp_path)
    events: list[PreparationProgress] = []
    result = RepairPreparationService(
        progress_observer=events.append
    ).prepare_bound_application_repair(
        layout=InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64),
        release_source=source,
    )
    for stage in (PreparationStage.APPLICATION, PreparationStage.LAUNCHER):
        measured = [
            event
            for event in events
            if event.stage is stage and event.transfer is not None
        ]
        assert len(measured) > 2
        assert measured[0].completed_fraction < measured[-1].completed_fraction
        assert all(event.completed_fraction < 1 for event in measured)
        assert measured[-1].transfer is not None
        assert (
            measured[-1].transfer.completed_bytes == measured[-1].transfer.total_bytes
        )
    fractions = [event.completed_fraction for event in events]
    assert fractions == sorted(fractions)
    assert events[-1].stage is PreparationStage.READY
    assert PreparedRepairRequest.load(result.request_path) == result.request


@pytest.mark.platforms("windows")
def test_native_preparation_stages_real_archives_and_preserves_active_files(
    tmp_path: Path,
) -> None:
    """Verify child success through production bootstrap, framing and native cleanup."""
    source = _create_release(tmp_path)
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    layout.root.mkdir()
    sentinel = layout.root / "active.txt"
    sentinel.write_bytes(b"preserve existing installation")
    operation = RepairPreparationOperation(
        layout=layout,
        release_source=source,
        scope=RepairScope.APPLICATION,
    )
    events: list[PreparationProgress] = []
    result = operation.run(progress_observer=events.append)
    assert operation.safe_to_close
    request = result.request
    assert request.version == "1.2.3"
    assert PreparedRepairRequest.load(result.request_path) == request
    assert request.install_root == layout.root
    assert request.scope == RepairScope.APPLICATION
    assert request.helper_bundle_dir is not None
    assert request.helper_bundle_dir.is_dir()
    assert events[0].stage is PreparationStage.RELEASE
    assert events[-1].stage is PreparationStage.READY
    assert any(event.transfer is not None for event in events)
    assert sentinel.read_bytes() == b"preserve existing installation"
    assert list((layout.root / ".repair").glob("preparation-*.json")) == []


def test_cancel_before_preparation_admission_creates_no_control_state(
    tmp_path: Path,
) -> None:
    """Honor Close before startup without creating an installation or spawning a child."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    operation = RepairPreparationOperation(
        layout=layout,
        release_source=LocalFolderReleaseSource(tmp_path),
        scope=RepairScope.APPLICATION,
    )
    operation.request_cancel()
    events: list[PreparationProgress] = []
    with pytest.raises(RepairProcessCancelled):
        operation.run(progress_observer=events.append)
    assert operation.safe_to_close
    assert not layout.root.exists()
    assert events == []


@pytest.mark.platforms("windows")
def test_preparation_failure_retires_private_input(tmp_path: Path) -> None:
    """Keep transient control files from accumulating after ordinary source failure."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    operation = RepairPreparationOperation(
        layout=layout,
        release_source=LocalFolderReleaseSource(tmp_path),
        scope=RepairScope.APPLICATION,
    )
    events: list[PreparationProgress] = []
    with pytest.raises(RepairProcessError, match="manifest"):
        operation.run(progress_observer=events.append)
    assert operation.safe_to_close
    assert list((layout.root / ".repair").glob("preparation-*.json")) == []
    assert [event.stage for event in events] == [PreparationStage.RELEASE]
