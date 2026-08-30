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

"""Acquire, verify, extract, and install the launcher-managed uv executable."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningError
from sugarsubstitute_shared.launcher_update.archive import (
    SecureArchiveError,
    safe_extract_tar_gzip,
    safe_extract_zip,
)


class VerifiedUvExecutableProvider:
    """Provide uv from an existing, bundled, or checksummed archive source."""

    def __init__(
        self,
        *,
        bundled_uv_path: Path | None = None,
        uv_archive_asset: ReleaseAsset | None = None,
        downloader: AssetDownloader | None = None,
    ) -> None:
        """Store trusted uv sources and the release-asset downloader."""

        self._bundled_uv_path = bundled_uv_path
        self._uv_archive_asset = uv_archive_asset
        self._downloader = downloader or AssetDownloader()

    def ensure(self, *, layout: InstallLayout) -> Path:
        """Ensure the standalone uv executable exists under runtime tools."""

        uv_executable = layout.uv_executable
        if uv_executable.is_file():
            return uv_executable
        if self._bundled_uv_path is not None:
            return _copy_uv_executable(
                source_path=self._bundled_uv_path,
                destination_path=uv_executable,
            )
        if self._uv_archive_asset is None:
            raise RuntimeProvisioningError(
                f"{layout.target.uv_executable_name} is missing and no bundled uv "
                "executable or verified uv archive is configured."
            )

        archive_path = layout.downloads_dir / "uv" / self._uv_archive_asset.filename
        self._downloader.download(
            asset=self._uv_archive_asset,
            destination_path=archive_path,
        )
        _verify_file_sha256(
            path=archive_path,
            expected_sha256=self._uv_archive_asset.sha256,
        )
        extracted_dir = layout.runtime_dir / "uv_extract"
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)
        try:
            _extract_uv_archive(
                archive_path=archive_path,
                destination_dir=extracted_dir,
            )
            extracted_uv = _find_uv_executable(
                extracted_dir,
                executable_name=layout.target.uv_executable_name,
            )
            return _copy_uv_executable(
                source_path=extracted_uv,
                destination_path=uv_executable,
            )
        finally:
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir)


def _find_uv_executable(extracted_dir: Path, *, executable_name: str) -> Path:
    """Find the target uv executable inside a safely extracted archive."""

    matches = [path for path in extracted_dir.rglob(executable_name) if path.is_file()]
    if not matches:
        raise RuntimeProvisioningError(
            f"Downloaded uv archive does not contain {executable_name}: {extracted_dir}"
        )
    return matches[0]


def _copy_uv_executable(*, source_path: Path, destination_path: Path) -> Path:
    """Copy a bundled uv executable into the launcher-managed runtime."""

    if not source_path.is_file():
        raise RuntimeProvisioningError(
            f"Bundled uv executable is missing: {source_path}"
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    destination_path.chmod(destination_path.stat().st_mode | 0o111)
    return destination_path


def _extract_uv_archive(*, archive_path: Path, destination_dir: Path) -> None:
    """Extract one supported official uv release archive safely."""

    try:
        if archive_path.name.endswith(".zip"):
            safe_extract_zip(
                zip_path=archive_path,
                destination_dir=destination_dir,
                symlink_policy="reject",
            )
            return
        if archive_path.name.endswith((".tar.gz", ".tgz")):
            safe_extract_tar_gzip(
                tar_path=archive_path, destination_dir=destination_dir
            )
            return
    except SecureArchiveError as error:
        raise RuntimeProvisioningError(str(error)) from error
    raise RuntimeProvisioningError(
        f"Unsupported uv archive format: {archive_path.name}"
    )


def _verify_file_sha256(*, path: Path, expected_sha256: str) -> None:
    """Verify a downloaded uv archive before extracting it."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_sha256.lower():
        raise RuntimeProvisioningError(f"uv archive SHA256 mismatch: {path}")
