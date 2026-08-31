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

"""Download, verify, extract, and validate application payload candidates."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import (
    PayloadInstallError,
    StagedAppPayload,
)
from sugarsubstitute_shared.launcher_update.archive import (
    SecureArchiveError,
    safe_extract_zip,
)


class AppPayloadStager:
    """Prepare a complete verified payload without replacing installed content."""

    def __init__(self, *, downloader: AssetDownloader | None = None) -> None:
        """Store the release-asset downloader."""

        self._downloader = downloader or AssetDownloader()

    def stage(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        destination_dir: Path,
    ) -> StagedAppPayload:
        """Stage one manifest payload inside the installation boundary."""

        root = layout.root.resolve()
        destination = destination_dir.resolve()
        if destination == root or not destination.is_relative_to(root):
            raise PayloadInstallError(
                f"Payload staging path escapes its installation: {destination}"
            )
        payload_path = layout.downloads_dir / manifest.version / manifest.app.filename
        self._downloader.download(asset=manifest.app, destination_path=payload_path)
        verify_sha256(path=payload_path, expected_sha256=manifest.app.sha256)
        _remove_directory(destination)
        extract_app_payload_archive(
            zip_path=payload_path,
            destination_dir=destination,
        )
        validate_app_payload(destination)
        return StagedAppPayload(version=manifest.version, staging_dir=destination)


def verify_sha256(*, path: Path, expected_sha256: str) -> None:
    """Fail when downloaded bytes do not match their manifest digest."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_sha256.lower():
        raise PayloadInstallError(f"SHA256 mismatch for payload: {path}")


def extract_app_payload_archive(*, zip_path: Path, destination_dir: Path) -> None:
    """Extract a validated application payload while rejecting symlinks."""

    try:
        safe_extract_zip(
            zip_path=zip_path,
            destination_dir=destination_dir,
            symlink_policy="reject",
        )
    except SecureArchiveError as error:
        raise PayloadInstallError(str(error)) from error


def validate_app_payload(app_dir: Path) -> None:
    """Verify that a staged payload contains every required application root."""

    required_files = (
        app_dir / "main.py",
        app_dir / "requirements.txt",
        app_dir / "sitecustomize.py",
    )
    required_dirs = (app_dir / "substitute", app_dir / "third_party")
    missing_files = [str(path) for path in required_files if not path.is_file()]
    missing_dirs = [str(path) for path in required_dirs if not path.is_dir()]
    if missing_files or missing_dirs:
        missing = ", ".join(missing_files + missing_dirs)
        raise PayloadInstallError(f"App payload is missing required paths: {missing}")


def _remove_directory(path: Path) -> None:
    """Remove one installer-owned staging directory when present."""

    if path.exists():
        shutil.rmtree(path)


__all__ = [
    "AppPayloadStager",
    "extract_app_payload_archive",
    "validate_app_payload",
    "verify_sha256",
]
