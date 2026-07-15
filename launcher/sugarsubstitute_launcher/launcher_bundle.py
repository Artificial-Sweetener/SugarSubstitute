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

"""Install the permanent launcher bundle into a selected app root."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import (
    PayloadInstallError,
    safe_extract_zip,
    verify_sha256,
)


INSTALLED_LAUNCHER_SUPPORT_DIR = Path("launcher-bin")


@dataclass(frozen=True, slots=True)
class LauncherBundleInstallResult:
    """Describe an installed launcher bundle."""

    executable_path: Path
    support_dir: Path


class LauncherBundleInstaller:
    """Download, verify, and install the permanent launcher bundle."""

    def __init__(self, *, downloader: AssetDownloader | None = None) -> None:
        """Store collaborators used to fetch launcher bundle assets."""

        self._downloader = downloader or AssetDownloader()

    def install(
        self, *, layout: InstallLayout, manifest: ReleaseManifest
    ) -> LauncherBundleInstallResult:
        """Install the manifest launcher bundle matching the layout target."""

        launcher_asset = manifest.launcher_for(layout.target)
        if launcher_asset is None:
            raise PayloadInstallError(
                "Release manifest does not include a launcher bundle."
            )

        downloads_dir = layout.downloads_dir / manifest.version
        bundle_path = downloads_dir / launcher_asset.filename
        self._downloader.download(asset=launcher_asset, destination_path=bundle_path)
        verify_sha256(path=bundle_path, expected_sha256=launcher_asset.sha256)

        staging_dir = downloads_dir / "launcher_bundle"
        _remove_directory(staging_dir)
        safe_extract_zip(zip_path=bundle_path, destination_dir=staging_dir)
        validate_launcher_bundle(staging_dir, layout=layout)
        _promote_launcher_bundle(staging_dir=staging_dir, layout=layout)
        return LauncherBundleInstallResult(
            executable_path=layout.executable_path,
            support_dir=layout.launcher_support_path,
        )


def validate_launcher_bundle(bundle_dir: Path, *, layout: InstallLayout) -> None:
    """Verify that an extracted bundle matches the target's PyInstaller shape."""

    executable_path = bundle_dir / layout.target.executable_relative_path
    support_dir = bundle_dir / layout.target.support_relative_path
    if not executable_path.is_file():
        raise PayloadInstallError(
            "Launcher bundle is missing required executable: "
            f"{layout.target.executable_relative_path}"
        )
    if not support_dir.is_dir():
        raise PayloadInstallError(
            "Launcher bundle must include an on-disk runtime support directory."
        )

    allowed_roots = (
        {
            layout.target.executable_relative_path.name,
            str(INSTALLED_LAUNCHER_SUPPORT_DIR),
        }
        if layout.target.bundle_root == Path(".")
        else {layout.target.bundle_root.name}
    )
    unexpected_roots = sorted(
        path.name for path in bundle_dir.iterdir() if path.name not in allowed_roots
    )
    if unexpected_roots:
        names = ", ".join(unexpected_roots)
        raise PayloadInstallError(f"Launcher bundle contains unexpected roots: {names}")


def _promote_launcher_bundle(*, staging_dir: Path, layout: InstallLayout) -> None:
    """Copy launcher bundle files into the install root."""

    layout.create_base_directories()
    if layout.target.bundle_root == Path("."):
        _replace_path(
            source_path=staging_dir / layout.target.executable_relative_path,
            destination_path=layout.executable_path,
        )
        _replace_path(
            source_path=staging_dir / layout.target.support_relative_path,
            destination_path=layout.launcher_support_path,
        )
        return
    _replace_path(
        source_path=staging_dir / layout.target.bundle_root,
        destination_path=layout.bundle_path,
    )


def _replace_path(*, source_path: Path, destination_path: Path) -> None:
    """Replace one installed launcher bundle path."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.is_dir():
        shutil.rmtree(destination_path)
    elif destination_path.exists():
        destination_path.unlink()

    if source_path.is_dir():
        shutil.copytree(source_path, destination_path)
    else:
        shutil.copy2(source_path, destination_path)


def _remove_directory(path: Path) -> None:
    """Remove one launcher-owned staging directory when present."""

    if path.exists():
        shutil.rmtree(path)
