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

"""Define persisted launcher update records and release inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)

LAUNCHER_INSTALLATION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class LauncherBundleAsset:
    """Describe one checksum-pinned launcher bundle archive."""

    filename: str
    url: str
    sha256: str
    size_bytes: int | None

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse a launcher bundle asset from a manifest value."""

        if not isinstance(payload, dict):
            raise ValueError("Launcher bundle asset must be a JSON object.")
        size_bytes = payload.get("size_bytes")
        if size_bytes is not None and not isinstance(size_bytes, int):
            raise ValueError("Launcher bundle size_bytes must be an integer.")
        return cls(
            filename=_required_string(payload, "filename"),
            url=_required_string(payload, "url"),
            sha256=_required_sha256(payload, "sha256"),
            size_bytes=size_bytes,
        )


@dataclass(frozen=True, slots=True)
class LauncherRelease:
    """Describe the launcher-specific portion of one release manifest."""

    channel: str
    version: str
    minimum_launcher_version: str
    asset: LauncherBundleAsset

    @classmethod
    def from_manifest_json(cls, payload: object, *, target_key: str) -> Self:
        """Parse the launcher release for one supported target."""

        if not isinstance(payload, dict):
            raise ValueError("Release manifest must be a JSON object.")
        launchers = payload.get("launchers")
        if not isinstance(launchers, dict):
            raise ValueError("Release manifest launchers must be a JSON object.")
        return cls(
            channel=_required_string(payload, "channel"),
            version=_required_string(payload, "version"),
            minimum_launcher_version=_required_string(
                payload,
                "minimum_launcher_version",
            ),
            asset=LauncherBundleAsset.from_json(launchers.get(target_key)),
        )


@dataclass(frozen=True, slots=True)
class LauncherInstallationRecord:
    """Record the launcher bundle successfully promoted into an install root."""

    version: str
    target_key: str
    schema_version: int = LAUNCHER_INSTALLATION_SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path) -> Self | None:
        """Load the installation record or return none for a legacy launcher."""

        if not path.is_file():
            return None
        payload = read_json_object(path)
        if payload.get("schema_version") != LAUNCHER_INSTALLATION_SCHEMA_VERSION:
            raise ValueError("Unsupported launcher installation record schema.")
        return cls(
            version=_required_string(payload, "version"),
            target_key=_required_string(payload, "target_key"),
        )

    def save(self, path: Path) -> None:
        """Persist the successful launcher installation record."""

        write_json_atomic(
            path,
            {
                "schema_version": self.schema_version,
                "target_key": self.target_key,
                "version": self.version,
            },
        )


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read one nonempty string from a decoded object."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Required string field is missing: {key}")
    return value


def _required_sha256(payload: dict[str, Any], key: str) -> str:
    """Read one normalized SHA256 digest."""

    value = _required_string(payload, key).lower()
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"Required SHA256 field is invalid: {key}")
    return value


__all__ = [
    "LAUNCHER_INSTALLATION_SCHEMA_VERSION",
    "LauncherBundleAsset",
    "LauncherInstallationRecord",
    "LauncherRelease",
]
