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

"""Verify release connectivity through the launcher's production HTTPS stack."""

from __future__ import annotations

from pathlib import Path
import tempfile

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.payload import verify_sha256
from launcher.sugarsubstitute_launcher.platforms import detect_launcher_target
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource
from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset


class ReleaseConnectivityVerifier:
    """Prove manifest and asset access without changing an installation."""

    def __init__(
        self,
        *,
        downloader: AssetDownloader | None = None,
        launcher_downloader: LauncherBundleDownloader | None = None,
    ) -> None:
        """Store the production app and launcher downloaders used by the probe."""

        self._downloader = downloader or AssetDownloader()
        self._launcher_downloader = launcher_downloader or LauncherBundleDownloader()

    def verify(self, *, release_source: ReleaseSource) -> None:
        """Download and verify current app and launcher assets from one source."""

        manifest = release_source.load_manifest()
        launcher_asset = manifest.launcher_for(detect_launcher_target())
        if launcher_asset is None:
            raise ValueError(
                "Release manifest does not include this platform launcher."
            )
        with tempfile.TemporaryDirectory(
            prefix="sugarsubstitute-connectivity-"
        ) as root:
            temporary_root = Path(root)
            destination = temporary_root / manifest.app.filename
            self._downloader.download(
                asset=manifest.app,
                destination_path=destination,
            )
            verify_sha256(
                path=destination,
                expected_sha256=manifest.app.sha256,
            )
            launcher_destination = (
                temporary_root / f"launcher-{launcher_asset.filename}"
            )
            self._launcher_downloader.download(
                asset=LauncherBundleAsset(
                    filename=launcher_asset.filename,
                    url=launcher_asset.url,
                    sha256=launcher_asset.sha256,
                    size_bytes=launcher_asset.size_bytes,
                ),
                destination=launcher_destination,
            )
            verify_sha256(
                path=launcher_destination,
                expected_sha256=launcher_asset.sha256,
            )
