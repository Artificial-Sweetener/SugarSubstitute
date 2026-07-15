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

"""Define standalone cube discovery and loading repository contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from substitute.domain.cube_library import (
    CubeIconDescriptor,
    CubeSourceMetadata,
)
from substitute.domain.common import JsonObject


@dataclass(frozen=True)
class CubeCatalogRecord:
    """Represent one selectable cube with canonical identity and display labels."""

    cube_id: str
    version: str
    display_name: str
    icon: CubeIconDescriptor | None = None
    description: str = ""
    source: CubeSourceMetadata | None = None
    supported_models: tuple[str, ...] = ()
    content_hash: str = ""
    updated_at: str = ""
    catalog_revision: str = ""


@dataclass(frozen=True)
class CubeCatalogSnapshot:
    """Represent a picker-facing cube catalog snapshot and freshness state."""

    entries: list[CubeCatalogRecord]
    state: Literal["missing", "fresh", "stale", "loading", "error"]
    source_timestamp: float | None = None
    error: str | None = None
    catalog_revision: str = ""


@dataclass(frozen=True)
class CubeDefinitionRecord:
    """Represent one loaded cube artifact returned by infrastructure."""

    cube_id: str
    version: str
    display_name: str
    graph: JsonObject
    content_hash: str
    source: CubeSourceMetadata
    artifact_label: str
    icon: CubeIconDescriptor | None = None
    local_path: Path | None = None
    catalog_revision: str = ""


@runtime_checkable
class CubeRepository(Protocol):
    """Describe cube load/list operations required by application services."""

    def load_cube(self, cube_id: str) -> CubeDefinitionRecord:
        """Load one standalone cube by canonical cube id."""

    def load_cube_version(self, cube_id: str, version: str) -> CubeDefinitionRecord:
        """Load one standalone cube by selected version."""

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Schedule best-effort warming for one standalone cube version."""

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """List versions available for one standalone cube id."""

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """List selectable cubes with canonical lookup names and display labels."""


@runtime_checkable
class CachedCubeCatalogRepository(Protocol):
    """Describe repositories that expose cached picker catalog snapshots."""

    def cached_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return the current cached catalog without refreshing infrastructure."""

    def refresh_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Refresh infrastructure catalog data and return the resulting snapshot."""

    def invalidate_cache(self) -> None:
        """Discard cached catalog data after an app-owned library mutation."""


__all__ = [
    "CubeCatalogRecord",
    "CubeCatalogSnapshot",
    "CubeDefinitionRecord",
    "CachedCubeCatalogRepository",
    "CubeRepository",
]
