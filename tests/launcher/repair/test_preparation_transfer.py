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

from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType
import zipfile

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
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


@dataclass(frozen=True)
class ReleaseSource:
    """Expose synthetic checksum-pinned archives without network access."""

    manifest: ReleaseManifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the immutable local test release."""
        return self.manifest


def test_real_preparation_reports_transfer_before_staging_is_complete(
    tmp_path: Path,
) -> None:
    """Deliver measured events from both composed downloaders and retain readiness ordering."""
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
    assets: list[ReleaseAsset] = []
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
            ReleaseAsset(
                path.name,
                path.as_uri(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_size,
            )
        )
    manifest = ReleaseManifest(
        schema_version=2,
        channel="stable",
        version="1.2.3",
        minimum_launcher_version="1.0.0",
        app=assets[0],
        launchers=MappingProxyType({WINDOWS_X64.key: assets[1]}),
        installers=MappingProxyType({}),
    )
    events: list[PreparationProgress] = []
    result = RepairPreparationService(
        progress_observer=events.append
    ).prepare_bound_application_repair(
        layout=InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64),
        release_source=ReleaseSource(manifest),
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
