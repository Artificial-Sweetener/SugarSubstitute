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

"""Parse release manifests used by launcher release sources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Self

from launcher.sugarsubstitute_launcher.platforms import (
    InstallerFormat,
    LauncherTarget,
    launcher_target_for_key,
)


MANIFEST_SCHEMA_VERSION = 2
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({1, MANIFEST_SCHEMA_VERSION})


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Describe one downloadable release artifact."""

    filename: str
    url: str
    sha256: str
    size_bytes: int | None

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse a release asset from a decoded manifest object."""

        if not isinstance(payload, dict):
            raise ValueError("Release asset must be a JSON object.")
        filename = _required_string(payload, "filename")
        url = _required_string(payload, "url")
        sha256 = _required_string(payload, "sha256")
        size_bytes = payload.get("size_bytes")
        if size_bytes is not None and not isinstance(size_bytes, int):
            raise ValueError("Release asset size_bytes must be an integer.")
        return cls(
            filename=filename,
            url=url,
            sha256=sha256,
            size_bytes=size_bytes,
        )


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Represent one launcher release manifest."""

    schema_version: int
    channel: str
    version: str
    minimum_launcher_version: str
    app: ReleaseAsset
    launchers: Mapping[str, ReleaseAsset]
    installers: Mapping[str, ReleaseAsset]

    def launcher_for(self, target: LauncherTarget) -> ReleaseAsset | None:
        """Return the installed-launcher asset for one supported target."""

        return self.launchers.get(target.key)

    def installer_for(
        self,
        target: LauncherTarget,
        installer_format: InstallerFormat | None = None,
    ) -> ReleaseAsset | None:
        """Return one public installer asset for a supported target."""

        selected_format = installer_format or target.primary_installer.format
        return self.installers.get(target.installer_key(selected_format))

    def installers_for(
        self, target: LauncherTarget
    ) -> Mapping[InstallerFormat, ReleaseAsset]:
        """Return every public installer asset published for one target."""

        return MappingProxyType(
            {
                specification.format: asset
                for specification in target.installers
                if (
                    asset := self.installers.get(
                        target.installer_key(specification.format)
                    )
                )
                is not None
            }
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load a release manifest from a local JSON file."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_json(payload)

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse a release manifest from decoded JSON data."""

        if not isinstance(payload, dict):
            raise ValueError("Release manifest must be a JSON object.")
        schema_version = _required_schema_version(payload)
        if schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
            raise ValueError(f"Unsupported release manifest schema: {schema_version}")
        return cls(
            schema_version=schema_version,
            channel=_required_string(payload, "channel"),
            version=_required_string(payload, "version"),
            minimum_launcher_version=_required_string(
                payload,
                "minimum_launcher_version",
            ),
            app=ReleaseAsset.from_json(payload.get("app")),
            launchers=_asset_map(payload=payload, key="launchers"),
            installers=_installer_asset_map(
                payload=payload,
                schema_version=schema_version,
            ),
        )


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read one required non-empty string field from a manifest object."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Manifest field must be a non-empty string: {key}")
    return value


def _required_schema_version(payload: dict[str, Any]) -> int:
    """Read the manifest schema version."""

    value = payload.get("schema_version")
    if not isinstance(value, int):
        raise ValueError("Manifest schema_version must be an integer.")
    return value


def _asset_map(*, payload: dict[str, Any], key: str) -> Mapping[str, ReleaseAsset]:
    """Parse one immutable platform-keyed release asset map."""

    raw_map = payload.get(key, {})
    if not isinstance(raw_map, dict):
        raise ValueError(f"Manifest field must be a JSON object: {key}")
    parsed = {
        str(platform_key): ReleaseAsset.from_json(asset_payload)
        for platform_key, asset_payload in raw_map.items()
    }
    return MappingProxyType(parsed)


def _installer_asset_map(
    *,
    payload: dict[str, Any],
    schema_version: int,
) -> Mapping[str, ReleaseAsset]:
    """Parse installer assets and normalize legacy target-only keys."""

    parsed = dict(_asset_map(payload=payload, key="installers"))
    if schema_version == MANIFEST_SCHEMA_VERSION:
        return MappingProxyType(parsed)
    normalized: dict[str, ReleaseAsset] = {}
    for target_key, asset in parsed.items():
        target = launcher_target_for_key(target_key)
        normalized[target.installer_key(target.primary_installer.format)] = asset
    return MappingProxyType(normalized)
