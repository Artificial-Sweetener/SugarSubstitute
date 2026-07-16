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

"""Download launcher bundles through the app and launcher shared boundary."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import ParseResult, unquote, urlparse
import urllib.request

from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset


class LauncherBundleDownloadError(RuntimeError):
    """Report a launcher bundle download that cannot be trusted."""


class LauncherBundleDownloader:
    """Download HTTPS or local test assets through an atomic partial file."""

    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        """Store the explicit remote request timeout."""

        self._timeout_seconds = timeout_seconds

    def download(self, *, asset: LauncherBundleAsset, destination: Path) -> Path:
        """Fetch one bundle and validate its declared size before promotion."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(f"{destination.suffix}.partial")
        partial.unlink(missing_ok=True)
        parsed = urlparse(asset.url)
        try:
            if parsed.scheme == "https":
                request = urllib.request.Request(asset.url, method="GET")
                with (
                    urllib.request.urlopen(
                        request,
                        timeout=self._timeout_seconds,
                    ) as response,
                    partial.open("wb") as output,
                ):
                    shutil.copyfileobj(response, output)
            elif parsed.scheme == "file":
                source = _file_url_path(parsed)
                if not source.is_file():
                    raise LauncherBundleDownloadError(
                        f"Launcher bundle does not exist: {source}"
                    )
                shutil.copyfile(source, partial)
            else:
                raise LauncherBundleDownloadError(
                    "Launcher bundle URLs must use HTTPS."
                )
            if (
                asset.size_bytes is not None
                and partial.stat().st_size != asset.size_bytes
            ):
                raise LauncherBundleDownloadError(
                    f"Launcher bundle size mismatch: {asset.filename}"
                )
            destination.unlink(missing_ok=True)
            partial.replace(destination)
            return destination
        except Exception:
            partial.unlink(missing_ok=True)
            raise


def _file_url_path(parsed: ParseResult) -> Path:
    """Convert one parsed file URL into its platform-native path."""

    path = unquote(parsed.path)
    if parsed.netloc:
        path = f"//{parsed.netloc}{path}"
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


__all__ = ["LauncherBundleDownloadError", "LauncherBundleDownloader"]
