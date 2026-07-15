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

"""Define the active-target Cube Library client contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.cube_library import (
    CubeCatalog,
    CubeDependencyRepairRequest,
    CubeDependencyRepairResult,
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackPreflight,
    CubePackRecord,
    LoadedCubeArtifact,
)
from substitute.domain.common import JsonObject


@runtime_checkable
class CubeLibraryClient(Protocol):
    """Describe HTTP client operations used by Cube Library consumers."""

    def get_status(self) -> CubeLibraryStatus | None:
        """Return target Cube Library status, or ``None`` when unavailable."""

    def get_catalog(self) -> CubeCatalog | None:
        """Return the active target catalog, or ``None`` when unavailable."""

    def load_cube(self, cube_id: str) -> LoadedCubeArtifact | None:
        """Return one cube artifact, or ``None`` when unavailable."""

    def load_cube_payload(self, cube_id: str) -> JsonObject | None:
        """Return one raw cube artifact payload, or ``None`` when unavailable."""

    def load_cube_version(
        self, cube_id: str, version: str
    ) -> LoadedCubeArtifact | None:
        """Return one versioned cube artifact, or ``None`` when unavailable."""

    def load_cube_version_payload(
        self, cube_id: str, version: str
    ) -> JsonObject | None:
        """Return one raw versioned artifact payload, or ``None`` when unavailable."""

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Schedule best-effort warming for one cube version artifact."""

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return versions available for one cube id."""

    def list_packs(self) -> tuple[CubePackRecord, ...]:
        """Return tracked Cube Packs for the active target."""

    def preflight_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
    ) -> CubePackPreflight | None:
        """Return candidate Cube Pack preflight results."""

    def add_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
        enabled: bool,
        auto_update: bool,
        sync_immediately: bool,
    ) -> CubePackRecord | None:
        """Track one Cube Pack on the active target."""

    def update_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str | None,
        enabled: bool | None,
        auto_update: bool | None,
    ) -> CubePackRecord | None:
        """Update one tracked Cube Pack on the active target."""

    def remove_pack(self, *, owner: str, repo: str) -> bool:
        """Remove one tracked Cube Pack from the active target."""

    def sync_pack(self, *, owner: str, repo: str) -> CubePackRecord | None:
        """Synchronously sync one tracked Cube Pack on the active target."""

    def sync_all_packs(self) -> tuple[CubePackRecord, ...]:
        """Synchronously sync all enabled Cube Packs on the active target."""

    def get_readiness(self) -> CubeLibraryReadiness | None:
        """Return read-only dependency readiness for the active target."""

    def get_dependency_readiness(self) -> CubeLibraryReadiness | None:
        """Return install-capable dependency readiness for the active target."""

    def repair_dependencies(
        self,
        request: CubeDependencyRepairRequest,
    ) -> CubeDependencyRepairResult | None:
        """Repair approved Cube Library dependencies on the active target."""

    def sync_and_check(
        self,
        request: CubeDependencySyncAndCheckRequest,
    ) -> CubeDependencySyncAndCheckResult | None:
        """Run shared sync and dependency readiness orchestration."""


__all__ = ["CubeLibraryClient"]
