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

"""Download or copy release assets into launcher-managed staging paths."""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset


DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 60.0


class AssetDownloadError(RuntimeError):
    """Raised when a release asset cannot be downloaded safely."""


class AssetDownloader:
    """Fetch release assets from file or HTTPS URLs."""

    def __init__(
        self, *, timeout_seconds: float = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS
    ) -> None:
        """Store the network timeout used for remote asset downloads."""

        self._timeout_seconds = timeout_seconds

    def download(self, *, asset: ReleaseAsset, destination_path: Path) -> Path:
        """Download one asset into a partial file before final promotion."""

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = destination_path.with_name(f"{destination_path.name}.partial")
        if partial_path.exists():
            partial_path.unlink()

        parsed_url = urlparse(asset.url)
        if parsed_url.scheme == "file":
            source_path = Path(url2pathname(parsed_url.path))
            if not source_path.exists():
                raise AssetDownloadError(f"Release asset does not exist: {source_path}")
            shutil.copyfile(source_path, partial_path)
        elif parsed_url.scheme == "https":
            self._download_remote(asset.url, partial_path)
        elif parsed_url.scheme == "http":
            raise AssetDownloadError("Remote release asset URLs must use HTTPS.")
        else:
            raise AssetDownloadError(
                f"Unsupported release asset URL scheme: {asset.url}"
            )

        if (
            asset.size_bytes is not None
            and partial_path.stat().st_size != asset.size_bytes
        ):
            partial_path.unlink(missing_ok=True)
            raise AssetDownloadError(f"Release asset size mismatch: {asset.filename}")
        if destination_path.exists():
            destination_path.unlink()
        partial_path.replace(destination_path)
        return destination_path

    def _download_remote(self, url: str, partial_path: Path) -> None:
        """Download one remote asset with an explicit timeout."""

        request = urllib.request.Request(url, method="GET")
        with (
            urllib.request.urlopen(request, timeout=self._timeout_seconds) as response,
            partial_path.open("wb") as destination,
        ):
            shutil.copyfileobj(response, destination)
