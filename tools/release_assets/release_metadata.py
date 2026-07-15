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

"""Build manifest metadata and checksums for release artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from launcher.sugarsubstitute_launcher.manifest import MANIFEST_SCHEMA_VERSION
from tools.release_assets.models import ReleaseAsset


def write_manifest(
    *,
    manifest_path: Path,
    version: str,
    channel: str,
    minimum_launcher_version: str,
    app_asset: ReleaseAsset,
    launcher_assets: Mapping[str, ReleaseAsset],
    installer_assets: Mapping[str, ReleaseAsset],
) -> None:
    """Write the release manifest consumed by launcher release sources."""

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "channel": channel,
        "version": version,
        "minimum_launcher_version": minimum_launcher_version,
        "app": app_asset.to_json(),
        "launchers": {key: asset.to_json() for key, asset in launcher_assets.items()},
        "installers": {key: asset.to_json() for key, asset in installer_assets.items()},
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_checksums(
    *,
    checksums_path: Path,
    assets: Mapping[str, ReleaseAsset],
) -> None:
    """Write a stable checksum file for release-channel assets."""

    lines = [
        f"{asset.sha256}  {asset.filename}"
        for asset in sorted(assets.values(), key=lambda value: value.filename)
    ]
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def release_asset_for_path(
    path: Path,
    *,
    asset_base_url: str | None = None,
) -> ReleaseAsset:
    """Return checksum, size, and URL metadata for one artifact path."""

    resolved_path = path.resolve()
    asset_url = (
        f"{asset_base_url.rstrip('/')}/{resolved_path.name}"
        if asset_base_url
        else resolved_path.as_uri()
    )
    return ReleaseAsset(
        filename=resolved_path.name,
        url=asset_url,
        sha256=sha256_file(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def sha256_file(path: Path) -> str:
    """Hash one file with SHA256 without loading it fully into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assets_for_checksums(
    *,
    app_asset: ReleaseAsset,
    launcher_assets: Mapping[str, ReleaseAsset],
    installer_assets: Mapping[str, ReleaseAsset],
) -> dict[str, ReleaseAsset]:
    """Index every downloadable artifact by filename for checksumming."""

    assets = {app_asset.filename: app_asset}
    assets.update((asset.filename, asset) for asset in launcher_assets.values())
    assets.update((asset.filename, asset) for asset in installer_assets.values())
    return assets
