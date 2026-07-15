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

"""Read and write launcher-owned configuration files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


CONFIG_SCHEMA_VERSION = 1
DEFAULT_RELEASE_MANIFEST_URL = (
    "https://github.com/Artificial-Sweetener/SugarSubstitute/"
    "releases/latest/download/manifest.json"
)
RELEASE_SOURCE_KIND_GITHUB: Literal["github_release_manifest"] = (
    "github_release_manifest"
)


@dataclass(frozen=True, slots=True)
class UpdateCheckConfig:
    """Describe automatic update-check preferences owned by the launcher."""

    enabled: bool = True
    frequency: str = "daily"

    def to_json(self) -> dict[str, bool | str]:
        """Return a JSON-safe update-check object."""

        return {
            "enabled": self.enabled,
            "frequency": self.frequency,
        }

    @classmethod
    def from_json(cls, value: object) -> Self:
        """Load update-check configuration from decoded JSON data."""

        if not isinstance(value, dict):
            return cls()
        enabled = value.get("enabled", True)
        frequency = value.get("frequency", "daily")
        return cls(
            enabled=enabled if isinstance(enabled, bool) else True,
            frequency=frequency if isinstance(frequency, str) else "daily",
        )


@dataclass(frozen=True, slots=True)
class ReleaseSourceConfig:
    """Describe the persisted upstream release manifest source."""

    kind: Literal["github_release_manifest"]
    manifest_url: str

    @classmethod
    def default(cls) -> Self:
        """Return the production GitHub release manifest source."""

        return cls(
            kind=RELEASE_SOURCE_KIND_GITHUB,
            manifest_url=DEFAULT_RELEASE_MANIFEST_URL,
        )

    def to_json(self) -> dict[str, str]:
        """Return a JSON-safe release source object."""

        return {
            "kind": self.kind,
            "manifest_url": self.manifest_url,
        }

    @classmethod
    def from_json(cls, value: object) -> Self:
        """Load release source configuration from decoded JSON data."""

        if not isinstance(value, dict):
            raise ValueError("Launcher release_source must be a JSON object.")
        kind = value.get("kind")
        if kind != RELEASE_SOURCE_KIND_GITHUB:
            raise ValueError(f"Unsupported launcher release source kind: {kind}")
        manifest_url = value.get("manifest_url")
        if not isinstance(manifest_url, str) or not manifest_url:
            raise ValueError("Launcher release_source manifest_url must be a string.")
        return cls(kind=RELEASE_SOURCE_KIND_GITHUB, manifest_url=manifest_url)


@dataclass(frozen=True, slots=True)
class LauncherConfig:
    """Represent persisted launcher install and update configuration."""

    schema_version: int
    install_root: Path
    app_dir: Path
    runtime_python: Path
    channel: str
    update_check: UpdateCheckConfig
    release_source: ReleaseSourceConfig | None

    @classmethod
    def from_layout(
        cls,
        *,
        layout: InstallLayout,
        channel: str = "stable",
        update_check: UpdateCheckConfig | None = None,
        release_source: ReleaseSourceConfig | None = ReleaseSourceConfig.default(),
    ) -> Self:
        """Create default launcher config for one install layout."""

        return cls(
            schema_version=CONFIG_SCHEMA_VERSION,
            install_root=layout.root,
            app_dir=layout.app_dir,
            runtime_python=layout.runtime_python,
            channel=channel,
            update_check=update_check or UpdateCheckConfig(),
            release_source=release_source,
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load launcher config from disk and reject unsupported schemas."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Launcher config must be a JSON object: {path}")
        schema_version = payload.get("schema_version")
        if schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(f"Unsupported launcher config schema: {schema_version}")
        return cls.from_json(payload)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        """Build launcher config from a decoded schema-versioned object."""

        return cls(
            schema_version=CONFIG_SCHEMA_VERSION,
            install_root=Path(_required_string(payload, "install_root")),
            app_dir=Path(_required_string(payload, "app_dir")),
            runtime_python=Path(_required_string(payload, "runtime_python")),
            channel=_optional_string(payload, "channel", "stable"),
            update_check=UpdateCheckConfig.from_json(payload.get("update_check")),
            release_source=_release_source_from_payload(payload),
        )

    def save(self, path: Path) -> None:
        """Persist launcher config using stable formatted JSON."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def to_json(self) -> dict[str, object]:
        """Return the JSON-safe launcher config object."""

        return {
            "schema_version": self.schema_version,
            "install_root": str(self.install_root),
            "app_dir": str(self.app_dir),
            "runtime_python": str(self.runtime_python),
            "channel": self.channel,
            "update_check": self.update_check.to_json(),
            "release_source": (
                self.release_source.to_json()
                if self.release_source is not None
                else None
            ),
        }


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read one required string from a decoded config object."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Launcher config field must be a non-empty string: {key}")
    return value


def _optional_string(payload: dict[str, Any], key: str, default: str) -> str:
    """Read one optional string from a decoded config object."""

    value = payload.get(key, default)
    return value if isinstance(value, str) and value else default


def _release_source_from_payload(
    payload: dict[str, Any],
) -> ReleaseSourceConfig | None:
    """Load persisted release source while upgrading old configs to production."""

    if "release_source" not in payload:
        return ReleaseSourceConfig.default()
    value = payload["release_source"]
    if value is None:
        return None
    return ReleaseSourceConfig.from_json(value)
