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

"""Install and validate replaceable SugarSubstitute app payloads."""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from sugarsubstitute_shared.launcher_update.archive import (
    SecureArchiveError,
    safe_extract_zip,
)


_LOGGER = logging.getLogger(__name__)


class PayloadInstallError(RuntimeError):
    """Raised when the app payload cannot be installed safely."""


@dataclass(frozen=True, slots=True)
class AppPayloadInstallResult:
    """Describe an installed app payload version."""

    version: str
    app_dir: Path


class AppPayloadInstaller:
    """Download, verify, extract, and promote source app payloads."""

    def __init__(self, *, downloader: AssetDownloader | None = None) -> None:
        """Store collaborators used for app payload installation."""

        self._downloader = downloader or AssetDownloader()

    def install(
        self, *, layout: InstallLayout, manifest: ReleaseManifest
    ) -> AppPayloadInstallResult:
        """Install the app payload from a release manifest into the layout."""

        downloads_dir = layout.downloads_dir / manifest.version
        payload_path = downloads_dir / manifest.app.filename
        _LOGGER.info(
            "Downloading app payload archive.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )
        self._downloader.download(asset=manifest.app, destination_path=payload_path)
        _LOGGER.info(
            "Downloaded app payload archive.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )
        verify_sha256(path=payload_path, expected_sha256=manifest.app.sha256)
        _LOGGER.info(
            "Verified app payload archive.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )

        app_next_dir = layout.root / "app_next"
        app_previous_dir = layout.root / "app_previous"
        _remove_directory(app_next_dir)
        _LOGGER.info(
            "Extracting app payload archive.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )
        extract_app_payload_archive(
            zip_path=payload_path,
            destination_dir=app_next_dir,
        )
        _LOGGER.info(
            "Extracted app payload archive.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )
        validate_app_payload(app_next_dir)

        previous_created = False
        if layout.app_dir.exists():
            _remove_directory(app_previous_dir)
            layout.app_dir.replace(app_previous_dir)
            previous_created = True
        try:
            app_next_dir.replace(layout.app_dir)
        except OSError:
            if (
                previous_created
                and app_previous_dir.exists()
                and not layout.app_dir.exists()
            ):
                app_previous_dir.replace(layout.app_dir)
            raise
        _LOGGER.info(
            "Promoted app payload.",
            extra={"version": manifest.version, "asset": manifest.app.filename},
        )
        return AppPayloadInstallResult(version=manifest.version, app_dir=layout.app_dir)


def verify_sha256(*, path: Path, expected_sha256: str) -> None:
    """Fail when a downloaded payload hash does not match the manifest."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    if actual_sha256.lower() != expected_sha256.lower():
        raise PayloadInstallError(f"SHA256 mismatch for payload: {path}")


def extract_app_payload_archive(*, zip_path: Path, destination_dir: Path) -> None:
    """Extract a validated app payload while rejecting every symlink entry."""

    try:
        safe_extract_zip(
            zip_path=zip_path,
            destination_dir=destination_dir,
            symlink_policy="reject",
        )
    except SecureArchiveError as error:
        raise PayloadInstallError(str(error)) from error


def validate_app_payload(app_dir: Path) -> None:
    """Verify that extracted payload contains the minimum app entry files."""

    required_files = (
        app_dir / "main.py",
        app_dir / "requirements.txt",
        app_dir / "sitecustomize.py",
    )
    required_dirs = (
        app_dir / "substitute",
        app_dir / "third_party",
    )
    missing_files = [str(path) for path in required_files if not path.is_file()]
    missing_dirs = [str(path) for path in required_dirs if not path.is_dir()]
    if missing_files or missing_dirs:
        missing = ", ".join(missing_files + missing_dirs)
        raise PayloadInstallError(f"App payload is missing required paths: {missing}")


def _remove_directory(path: Path) -> None:
    """Remove one launcher-owned app staging directory when present."""

    if path.exists():
        shutil.rmtree(path)
