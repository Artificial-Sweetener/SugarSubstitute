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
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource


class ReleaseConnectivityVerifier:
    """Prove manifest and asset access without changing an installation."""

    def __init__(self, *, downloader: AssetDownloader | None = None) -> None:
        """Store the production asset downloader used by the probe."""

        self._downloader = downloader or AssetDownloader()

    def verify(self, *, release_source: ReleaseSource) -> None:
        """Download and verify the current app asset from one release source."""

        manifest = release_source.load_manifest()
        with tempfile.TemporaryDirectory(
            prefix="sugarsubstitute-connectivity-"
        ) as root:
            destination = Path(root) / manifest.app.filename
            self._downloader.download(
                asset=manifest.app,
                destination_path=destination,
            )
            verify_sha256(
                path=destination,
                expected_sha256=manifest.app.sha256,
            )
