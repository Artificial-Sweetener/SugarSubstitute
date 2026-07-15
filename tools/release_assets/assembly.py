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

"""Coordinate focused builders into one complete release channel."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from tools.release_assets.launcher_archive import prepare_installed_launcher_archive
from tools.release_assets.models import LocalReleaseBuildResult, PlatformReleaseInput
from tools.release_assets.payload import (
    APP_PAYLOAD_PREFIX,
    build_app_payload_zip,
    validate_output_dir,
    validate_repo_root,
)
from tools.release_assets.release_metadata import (
    assets_for_checksums,
    release_asset_for_path,
    write_checksums,
    write_manifest,
)


def build_local_release_channel(
    *,
    repo_root: Path,
    output_dir: Path,
    version: str,
    channel: str = "stable",
    minimum_launcher_version: str = "0.1.0",
    platform_inputs: Sequence[PlatformReleaseInput] = (),
    asset_base_url: str | None = None,
) -> LocalReleaseBuildResult:
    """Create an app payload, platform assets, manifest, and checksums."""

    resolved_repo_root = repo_root.resolve()
    resolved_output_dir = output_dir.resolve()
    validate_version(version)
    validate_repo_root(resolved_repo_root)
    validate_output_dir(repo_root=resolved_repo_root, output_dir=resolved_output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    app_zip_path = resolved_output_dir / f"{APP_PAYLOAD_PREFIX}{version}.zip"
    build_app_payload_zip(repo_root=resolved_repo_root, output_path=app_zip_path)
    app_asset = release_asset_for_path(app_zip_path, asset_base_url=asset_base_url)

    launcher_assets = {}
    installer_assets = {}
    for platform_input in platform_inputs:
        platform_input.validate()
        target = platform_input.target
        launcher_zip_path = (
            resolved_output_dir
            / f"{target.installer_payload_archive_prefix}{version}.zip"
        )
        prepare_installed_launcher_archive(
            launcher_source=platform_input.launcher_source.resolve(),
            output_path=launcher_zip_path,
            target=target,
        )
        launcher_assets[target.key] = release_asset_for_path(
            launcher_zip_path,
            asset_base_url=asset_base_url,
        )
        for installer_input in platform_input.installers:
            specification = target.installer(installer_input.format)
            installer_path = resolved_output_dir / specification.filename
            copy_public_installer(
                source_path=installer_input.source_path,
                output_path=installer_path,
            )
            installer_assets[target.installer_key(installer_input.format)] = (
                release_asset_for_path(
                    installer_path,
                    asset_base_url=asset_base_url,
                )
            )

    manifest_path = resolved_output_dir / "manifest.json"
    write_manifest(
        manifest_path=manifest_path,
        version=version,
        channel=channel,
        minimum_launcher_version=minimum_launcher_version,
        app_asset=app_asset,
        launcher_assets=launcher_assets,
        installer_assets=installer_assets,
    )
    checksums_path = resolved_output_dir / "checksums.txt"
    write_checksums(
        checksums_path=checksums_path,
        assets=assets_for_checksums(
            app_asset=app_asset,
            launcher_assets=launcher_assets,
            installer_assets=installer_assets,
        ),
    )
    return LocalReleaseBuildResult(
        app_zip_path=app_zip_path,
        manifest_path=manifest_path,
        checksums_path=checksums_path,
        app_asset=app_asset,
        launcher_assets=launcher_assets,
        installer_assets=installer_assets,
    )


def copy_public_installer(*, source_path: Path, output_path: Path) -> Path:
    """Copy one downloadable native installer into the release channel."""

    resolved_source_path = source_path.resolve()
    resolved_output_path = output_path.resolve()
    if not resolved_source_path.is_file():
        raise FileNotFoundError(f"Installer artifact does not exist: {source_path}")
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved_source_path, resolved_output_path)
    return resolved_output_path


def validate_version(version: str) -> None:
    """Reject empty or path-like version values before naming artifacts."""

    if not version.strip():
        raise ValueError("Release version must not be empty.")
    if any(character in version for character in ("/", "\\", ":")):
        raise ValueError(f"Release version must be a plain tag value: {version}")
