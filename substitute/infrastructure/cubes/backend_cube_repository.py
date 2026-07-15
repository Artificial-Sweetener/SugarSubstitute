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

"""Load SugarCubes from the active target's Cube Library API."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, time

from substitute.application.ports import CubeLibraryClient
from substitute.application.ports.cube_repository import (
    CubeCatalogRecord,
    CubeCatalogSnapshot,
    CubeDefinitionRecord,
)
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeIconDescriptor,
    LoadedCubeArtifact,
)
from substitute.shared.logging.logger import get_logger, log_timing
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("infrastructure.cubes.backend_cube_repository")


@dataclass(frozen=True)
class BackendCubeRepository:
    """Provide CubeRepository data from Substitute BackEnd Cube Library routes."""

    client: CubeLibraryClient
    _catalog_cache: CubeCatalog | None = field(default=None, init=False, repr=False)
    _catalog_cached_at: float | None = field(default=None, init=False, repr=False)

    def load_cube(self, cube_id: str) -> CubeDefinitionRecord:
        """Load one cube artifact from the active target by canonical id."""

        started_at = perf_counter()
        with trace_span("backend_cube_repository.load_cube", cube_id=cube_id):
            artifact = self.client.load_cube(cube_id)
        return self._definition_record_from_artifact(
            artifact=artifact,
            requested_cube_id=cube_id,
            started_at=started_at,
        )

    def load_cube_version(self, cube_id: str, version: str) -> CubeDefinitionRecord:
        """Load one cube artifact from the active target by selected version."""

        started_at = perf_counter()
        with trace_span(
            "backend_cube_repository.load_cube_version",
            cube_id=cube_id,
            cube_version=version,
        ):
            artifact = self.client.load_cube_version(cube_id, version)
        return self._definition_record_from_artifact(
            artifact=artifact,
            requested_cube_id=cube_id,
            started_at=started_at,
        )

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Schedule best-effort warming for one cube artifact version."""

        return self.client.prewarm_cube_version(cube_id, version)

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """List versions available for one cube id from the active target."""

        started_at = perf_counter()
        with trace_span("backend_cube_repository.list_cube_versions", cube_id=cube_id):
            versions = self.client.list_cube_versions(cube_id)
        log_timing(
            _LOGGER,
            "Listed backend cube versions",
            started_at=started_at,
            cube_id=cube_id,
            version_count=len(versions),
        )
        return versions

    def _definition_record_from_artifact(
        self,
        *,
        artifact: LoadedCubeArtifact | None,
        requested_cube_id: str,
        started_at: float,
    ) -> CubeDefinitionRecord:
        """Build a repository definition record from one loaded artifact."""

        if artifact is None:
            trace_mark(
                "backend_cube_repository.load_cube.missing",
                cube_id=requested_cube_id,
                artifact_returned=False,
            )
            raise FileNotFoundError(
                f"Cube '{requested_cube_id}' could not be loaded from the active Cube Library."
            )
        trace_mark(
            "backend_cube_repository.load_cube.loaded",
            cube_id=artifact.cube_id,
            artifact_returned=True,
            source_kind=artifact.source.kind,
            repo_ref=artifact.source.repo_ref,
        )
        record = CubeDefinitionRecord(
            cube_id=artifact.cube_id,
            version=artifact.version,
            display_name=artifact.display_name,
            graph=artifact.cube,
            content_hash=artifact.content_hash,
            source=artifact.source,
            artifact_label=f"Cube Library:{artifact.cube_id}",
            icon=artifact.icon or self._cached_catalog_icon(artifact.cube_id),
            local_path=None,
            catalog_revision=self._cached_catalog_revision(),
        )
        log_timing(
            _LOGGER,
            "Loaded backend cube artifact",
            started_at=started_at,
            cube_id=artifact.cube_id,
            cube_version=artifact.version,
            source_kind=artifact.source.kind,
            repo_ref=artifact.source.repo_ref,
        )
        return record

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """List selectable cubes, refreshing the target catalog on each picker open."""

        started_at = perf_counter()
        snapshot = self.refresh_catalog_snapshot()
        records = snapshot.entries
        log_timing(
            _LOGGER,
            "Listed backend cube catalog",
            started_at=started_at,
            cube_count=len(records),
            catalog_state=snapshot.state,
        )
        return records

    def cached_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return cached catalog entries without contacting the backend."""

        catalog = self._catalog_cache
        if catalog is None:
            return CubeCatalogSnapshot(entries=[], state="missing")
        return CubeCatalogSnapshot(
            entries=_catalog_records(catalog),
            state="fresh",
            source_timestamp=self._catalog_cached_at,
            catalog_revision=catalog.catalog_revision,
        )

    def refresh_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Refresh the in-memory catalog cache and return a selectable snapshot."""

        self.refresh_catalog()
        return self.cached_catalog_snapshot()

    def refresh_catalog(self) -> None:
        """Refresh the in-memory catalog cache from the active target."""

        started_at = perf_counter()
        catalog = self.client.get_catalog()
        if catalog is not None:
            object.__setattr__(self, "_catalog_cache", catalog)
            object.__setattr__(self, "_catalog_cached_at", time())
        log_timing(
            _LOGGER,
            "Refreshed backend cube catalog cache",
            started_at=started_at,
            refreshed=catalog is not None,
            cube_count=len(catalog.cubes) if catalog is not None else 0,
            catalog_revision=catalog.catalog_revision if catalog is not None else "",
        )

    def invalidate_cache(self) -> None:
        """Discard the in-memory catalog cache after target library mutations."""

        object.__setattr__(self, "_catalog_cache", None)
        object.__setattr__(self, "_catalog_cached_at", None)

    def _cached_catalog_icon(self, cube_id: str) -> CubeIconDescriptor | None:
        """Return a catalog icon descriptor cached for one cube id."""

        catalog = self._catalog_cache
        if catalog is None:
            return None
        for entry in catalog.cubes:
            if entry.cube_id == cube_id:
                return entry.icon
        return None

    def _cached_catalog_revision(self) -> str:
        """Return the cached catalog revision when available."""

        catalog = self._catalog_cache
        return catalog.catalog_revision if catalog is not None else ""


def _catalog_records(catalog: CubeCatalog) -> list[CubeCatalogRecord]:
    """Convert a backend catalog document into picker records."""

    return [
        CubeCatalogRecord(
            cube_id=entry.cube_id,
            version=entry.version,
            display_name=entry.display_name,
            description=entry.description,
            source=entry.source,
            icon=entry.icon,
            supported_models=entry.supported_models,
            content_hash=entry.content_hash,
            updated_at=entry.updated_at,
            catalog_revision=catalog.catalog_revision,
        )
        for entry in catalog.cubes
    ]
