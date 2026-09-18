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

"""Preserve installer-selected release sources across an inert preparation boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    VersionBoundReleaseSource,
)


@dataclass(frozen=True, slots=True)
class RepairPreparationSource:
    """Encode supported exact repair sources without executing them in the parent."""

    source: LocalFolderReleaseSource | VersionBoundReleaseSource

    @classmethod
    def capture(cls, source: ReleaseManifestSource) -> RepairPreparationSource:
        """Capture source identity without network access or manifest materialization."""
        if isinstance(source, LocalFolderReleaseSource):
            return cls(LocalFolderReleaseSource(source.root.absolute()))
        if isinstance(source, VersionBoundReleaseSource):
            return cls(source)
        raise TypeError("Unsupported repair source for supervised preparation.")

    def to_json(self) -> dict[str, object]:
        """Describe the exact source using inert values and explicit source identity."""
        if isinstance(self.source, LocalFolderReleaseSource):
            return {"kind": "local", "root": str(self.source.root)}
        return {
            "kind": "version_bound",
            "manifest_url": self.source.manifest_url,
            "expected_version": self.source.expected_version,
            "expected_channel": self.source.expected_channel,
            "update_manifest_url": self.source.update_manifest_url,
        }

    @classmethod
    def from_json(cls, value: object) -> RepairPreparationSource:
        """Reject incomplete worker input before constructing any provider adapter."""
        if not isinstance(value, dict):
            raise ValueError("Repair source must be an object.")
        kind = _required_text(value, "kind")
        if kind == "local":
            if set(value) != {"kind", "root"}:
                raise ValueError("Local repair source fields are invalid.")
            root = Path(_required_text(value, "root"))
            if not root.is_absolute():
                raise ValueError("Local repair source requires an absolute folder.")
            return cls(LocalFolderReleaseSource(root))
        if kind == "version_bound":
            if set(value) != {
                "kind",
                "manifest_url",
                "expected_version",
                "expected_channel",
                "update_manifest_url",
            }:
                raise ValueError("Version-bound repair source fields are invalid.")
            return cls(
                VersionBoundReleaseSource(
                    manifest_url=_required_text(value, "manifest_url"),
                    expected_version=_required_text(value, "expected_version"),
                    expected_channel=_required_text(value, "expected_channel"),
                    update_manifest_url=_required_text(value, "update_manifest_url"),
                )
            )
        raise ValueError("Unsupported repair source kind.")


def _required_text(payload: Mapping[object, object], field: str) -> str:
    """Require explicit nonempty values rather than inventing worker-side defaults."""
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"Repair source requires valid text for {field}.")
    return value
