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

"""Resolve release manifests from configured release sources."""

from __future__ import annotations

import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol
from urllib.parse import urlparse

from launcher.sugarsubstitute_launcher.config import (
    DEFAULT_RELEASE_MANIFEST_URL,
    RELEASE_SOURCE_KIND_GITHUB,
    ReleaseSourceConfig,
)
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from sugarsubstitute_shared.tls import SystemTrustTlsContext


class ReleaseSource(Protocol):
    """Load the latest release manifest for a launcher channel."""

    def load_manifest(self) -> ReleaseManifest:
        """Return the latest available release manifest."""


@dataclass(frozen=True, slots=True)
class LocalFolderReleaseSource:
    """Read release assets from a local development release-channel folder."""

    root: Path

    def load_manifest(self) -> ReleaseManifest:
        """Load `manifest.json` from this local release-channel root."""

        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Local release manifest does not exist: {manifest_path}"
            )
        return _with_folder_relative_assets(
            manifest=ReleaseManifest.load(manifest_path),
            release_root=self.root,
        )


@dataclass(frozen=True, slots=True)
class GitHubReleaseSource:
    """Read a release manifest from an HTTPS GitHub Release asset URL."""

    manifest_url: str
    timeout_seconds: float = 30.0
    tls_context: ssl.SSLContext = field(
        default_factory=SystemTrustTlsContext.create,
        repr=False,
        compare=False,
    )

    def load_manifest(self) -> ReleaseManifest:
        """Download and parse the GitHub-hosted release manifest."""

        _require_https_url(self.manifest_url, "release manifest")
        request = urllib.request.Request(self.manifest_url, method="GET")
        with urllib.request.urlopen(
            request,
            timeout=self.timeout_seconds,
            context=self.tls_context,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return ReleaseManifest.from_json(payload)


def release_source_from_config(
    config: ReleaseSourceConfig | None,
) -> ReleaseSource | None:
    """Create a concrete release source from persisted launcher config."""

    if config is None:
        return None
    if config.kind == RELEASE_SOURCE_KIND_GITHUB:
        return GitHubReleaseSource(config.manifest_url)
    raise ValueError(f"Unsupported launcher release source kind: {config.kind}")


def default_production_release_source() -> ReleaseSource:
    """Return the production GitHub release manifest source."""

    return GitHubReleaseSource(DEFAULT_RELEASE_MANIFEST_URL)


def release_source_config_for(source: ReleaseSource) -> ReleaseSourceConfig | None:
    """Return persisted config for production release sources."""

    if isinstance(source, GitHubReleaseSource):
        return ReleaseSourceConfig(
            kind=RELEASE_SOURCE_KIND_GITHUB,
            manifest_url=source.manifest_url,
        )
    return None


def _require_https_url(url: str, description: str) -> None:
    """Reject insecure remote release URLs."""

    if urlparse(url).scheme != "https":
        raise ValueError(f"Remote {description} URLs must use HTTPS.")


def _with_folder_relative_assets(
    *, manifest: ReleaseManifest, release_root: Path
) -> ReleaseManifest:
    """Resolve local release asset URLs from the manifest folder when present."""

    resolved_root = release_root.resolve()
    return ReleaseManifest(
        schema_version=manifest.schema_version,
        channel=manifest.channel,
        version=manifest.version,
        minimum_launcher_version=manifest.minimum_launcher_version,
        app=_with_folder_relative_asset(
            asset=manifest.app,
            release_root=resolved_root,
        ),
        launchers=_with_folder_relative_asset_map(
            assets=manifest.launchers,
            release_root=resolved_root,
        ),
        installers=_with_folder_relative_asset_map(
            assets=manifest.installers,
            release_root=resolved_root,
        ),
    )


def _with_folder_relative_asset_map(
    *,
    assets: Mapping[str, ReleaseAsset],
    release_root: Path,
) -> Mapping[str, ReleaseAsset]:
    """Resolve every local asset in one immutable platform map."""

    return MappingProxyType(
        {
            key: _with_folder_relative_asset(
                asset=asset,
                release_root=release_root,
            )
            for key, asset in assets.items()
        }
    )


def _with_folder_relative_asset(
    *, asset: ReleaseAsset, release_root: Path
) -> ReleaseAsset:
    """Prefer the asset file beside the local manifest over stale file URLs."""

    local_path = release_root / asset.filename
    if not local_path.is_file():
        return asset
    return ReleaseAsset(
        filename=asset.filename,
        url=local_path.resolve().as_uri(),
        sha256=asset.sha256,
        size_bytes=asset.size_bytes,
    )
