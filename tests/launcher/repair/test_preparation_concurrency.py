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

"""Exercise overlapping repair preparation with real archive staging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
from pathlib import Path
from threading import Barrier
from types import MappingProxyType
import zipfile

from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparationService,
)
from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


@dataclass(frozen=True)
class ReleaseSource:
    """Supply a pinned local manifest without network access."""

    manifest: ReleaseManifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the exact archive identities assigned to this preparation."""
        return self.manifest


def test_concurrent_repairs_preserve_both_complete_preparations(tmp_path: Path) -> None:
    """Isolate real downloads, app payloads, launcher bundles and request records."""
    ready = Barrier(2)

    class Downloader(AssetDownloader):
        """Synchronize completed downloads to expose shared destination races."""

        def download(self, *, asset: ReleaseAsset, destination_path: Path) -> Path:
            """Wait until both app archives are present before allowing extraction."""
            path = super().download(asset=asset, destination_path=destination_path)
            ready.wait(timeout=5)
            return path

    sources: list[ReleaseSource] = []
    for marker in ("first", "second"):
        directory = tmp_path / marker
        directory.mkdir()
        app = directory / "payload.zip"
        launcher = directory / "launcher.zip"
        with zipfile.ZipFile(app, "w") as archive:
            for path in (
                "main.py",
                "requirements.txt",
                "sitecustomize.py",
                "substitute/__init__.py",
                "third_party/NOTICE.md",
            ):
                archive.writestr(path, marker)
        with zipfile.ZipFile(launcher, "w") as archive:
            for path in (
                "SugarSubstitute.exe",
                "launcher-bin/LauncherUi.exe",
                "launcher-bin/Repair.exe",
                "launcher-bin/runtime.txt",
            ):
                archive.writestr(path, marker)
        assets = [
            ReleaseAsset(
                path.name,
                path.as_uri(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_size,
            )
            for path in (app, launcher)
        ]
        sources.append(
            ReleaseSource(
                ReleaseManifest(
                    schema_version=2,
                    channel="stable",
                    version="1.2.3",
                    minimum_launcher_version="1.0.0",
                    app=assets[0],
                    launchers=MappingProxyType({WINDOWS_X64.key: assets[1]}),
                    installers=MappingProxyType({}),
                )
            )
        )
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    service = RepairPreparationService(
        app_stager=AppPayloadStager(downloader=Downloader())
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(
                service.prepare_application_repair,
                layout=layout,
                release_source=source,
                expected_version="1.2.3",
            )
            for source in sources
        ]
        prepared = [future.result(timeout=15) for future in pending]
    assert len({item.request_path for item in prepared}) == 2
    for item, marker in zip(prepared, ("first", "second"), strict=True):
        assert (item.request.staged_app_dir / "main.py").read_text(
            encoding="utf-8"
        ) == marker
        assert (item.request.staged_launcher_dir / "SugarSubstitute.exe").read_text(
            encoding="utf-8"
        ) == marker
        assert item.request.helper_bundle_dir is not None
        assert (item.request.helper_bundle_dir / "SugarSubstitute.exe").read_text(
            encoding="utf-8"
        ) == marker
        assert item.request_path.exists()
