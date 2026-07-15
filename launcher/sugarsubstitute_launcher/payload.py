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
import shutil
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest


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
        self._downloader.download(asset=manifest.app, destination_path=payload_path)
        verify_sha256(path=payload_path, expected_sha256=manifest.app.sha256)

        app_next_dir = layout.root / "app_next"
        app_previous_dir = layout.root / "app_previous"
        _remove_directory(app_next_dir)
        safe_extract_zip(zip_path=payload_path, destination_dir=app_next_dir)
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


def safe_extract_zip(*, zip_path: Path, destination_dir: Path) -> None:
    """Extract a zip file while rejecting traversal and symlink entries."""

    destination_root = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            archive_name = _validated_archive_name(member)
            target_path = (destination_root / archive_name).resolve()
            if not target_path.is_relative_to(destination_root):
                raise PayloadInstallError(
                    f"Archive entry escapes destination: {member.filename}"
                )
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            archived_permissions = (member.external_attr >> 16) & 0o777
            if archived_permissions:
                target_path.chmod(archived_permissions)


def safe_extract_tar_gzip(*, tar_path: Path, destination_dir: Path) -> None:
    """Extract a gzip tar while rejecting links, devices, and traversal."""

    destination_root = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            raw_name = member.name.replace("\\", "/")
            archive_path = PurePosixPath(raw_name)
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise PayloadInstallError(
                    f"Archive entry has unsafe path: {member.name}"
                )
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise PayloadInstallError(
                    f"Archive entry has an unsupported type: {member.name}"
                )
            target_path = (destination_root / archive_path).resolve()
            if not target_path.is_relative_to(destination_root):
                raise PayloadInstallError(
                    f"Archive entry escapes destination: {member.name}"
                )
        archive.extractall(destination_dir, filter="data")


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


def _validated_archive_name(member: zipfile.ZipInfo) -> PurePosixPath:
    """Return a normalized archive name or reject unsafe entries."""

    if _is_symlink(member):
        raise PayloadInstallError(
            f"Archive entry must not be a symlink: {member.filename}"
        )
    raw_name = member.filename.replace("\\", "/")
    archive_path = PurePosixPath(raw_name)
    if archive_path.is_absolute() or ".." in archive_path.parts:
        raise PayloadInstallError(f"Archive entry has unsafe path: {member.filename}")
    if not archive_path.parts:
        raise PayloadInstallError("Archive entry has an empty path.")
    return archive_path


def _is_symlink(member: zipfile.ZipInfo) -> bool:
    """Return whether a zip member advertises itself as a Unix symlink."""

    file_type = stat.S_IFMT(member.external_attr >> 16)
    return file_type == stat.S_IFLNK


def _remove_directory(path: Path) -> None:
    """Remove one launcher-owned app staging directory when present."""

    if path.exists():
        shutil.rmtree(path)
