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

"""Provide application-layer orchestration for cube discovery and loading."""

from __future__ import annotations

import copy
from collections import OrderedDict
from collections.abc import Callable
import random
from dataclasses import dataclass
from threading import Lock
from time import perf_counter, time
from typing import Any, Mapping, MutableMapping, cast

from substitute.application.cubes.cube_picker_models import (
    CubePickerRole,
    CubeSearchTargetKind,
    CubeSearchTerm,
    CubePickerClassification,
    classify_cube_document,
)
from substitute.application.execution import BlockingSingleFlight
from substitute.application.cubes.persisted_input_overlay import (
    overlay_persisted_node_inputs,
)
from substitute.application.cubes.seed_initialization import (
    initialize_fresh_seed_controls,
)
from substitute.application.ports.cube_repository import (
    CachedCubeCatalogRepository,
    CubeCatalogRecord,
    CubeCatalogSnapshot,
    CubeRepository,
)
from substitute.application.ports.cube_classification_cache import (
    CachedCubePickerClassification,
    CachedCubeSearchTerm,
    CubeClassificationCacheKey,
    CubeClassificationCacheRepository,
)
from substitute.domain.cubes import (
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeIconDescriptor, CubeUpdatePolicy
from substitute.domain.recipes import merge_recipe_buffer
from substitute.domain.workflow import CubeState
from substitute.domain.workflow.cube_contract_validator import validate_cube_contract
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_timing,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("application.cubes.cube_load_service")
DEFAULT_CUBE_CATALOG_TTL_SECONDS = 30.0
_CLASSIFICATION_ALGORITHM_VERSION = 1
_LOADED_DEFINITION_ALGORITHM_VERSION = 1
_DEFAULT_DEFINITION_CACHE_MAXIMUM_ENTRIES = 128
_CUBE_PICKER_ROLES = {"start", "middle", "end", "unclassified"}
_CUBE_SEARCH_TARGET_KINDS = {
    "cube",
    "model",
    "pack",
    "node",
    "definition",
    "control",
    "source",
    "technical",
}


@dataclass(frozen=True)
class LoadedCubeDefinition:
    """Represent application-level loaded cube payload for runtime orchestration."""

    cube_id: str
    version: str
    display_name: str
    graph: JsonObject
    ui_payload: dict[str, object] | None
    icon: CubeIconDescriptor | None = None


@dataclass(frozen=True)
class LoadedCubeRuntime:
    """Represent fully prepared cube runtime state ready for workflow insertion."""

    cube_id: str
    version: str
    display_name: str
    cube_definition: JsonObject
    cube_buffer: JsonObject
    cube_state: CubeState
    ui_payload: dict[str, object] | None
    icon: CubeIconDescriptor | None = None


@dataclass(frozen=True)
class _LoadedDefinitionCacheKey:
    """Identify one process-cached loaded cube definition."""

    target_key: str
    catalog_revision: str
    cube_id: str
    cube_content_hash: str
    cube_version: str
    algorithm_version: int

    def stable_hash(self) -> str:
        """Return a deterministic key using the classification key serializer."""

        return CubeClassificationCacheKey(
            target_key=self.target_key,
            catalog_revision=self.catalog_revision,
            cube_id=self.cube_id,
            cube_content_hash=self.cube_content_hash,
            cube_version=self.cube_version,
            algorithm_version=self.algorithm_version,
        ).stable_hash()


def _loaded_definition_cache_trace_fields(
    key: _LoadedDefinitionCacheKey,
    *,
    cube_load_trace_id: str,
    cache_size: int | None = None,
    node_count: int | None = None,
    unique_class_count: int | None = None,
) -> dict[str, object]:
    """Return non-sensitive trace fields for one loaded definition cache key."""

    fields: dict[str, object] = {
        "target_key": key.target_key,
        "catalog_revision": key.catalog_revision,
        "cube_id": key.cube_id,
        "cube_version": key.cube_version,
        "content_hash": key.cube_content_hash,
        "algorithm_version": key.algorithm_version,
        "cube_load_trace_id": cube_load_trace_id,
    }
    if cache_size is not None:
        fields["cache_size"] = cache_size
    if node_count is not None:
        fields["node_count"] = node_count
    if unique_class_count is not None:
        fields["unique_class_count"] = unique_class_count
    return fields


class CubeLoadService:
    """Coordinate standalone cube loading behavior for presentation callsites."""

    def __init__(
        self,
        cube_repository: CubeRepository,
        *,
        catalog_ttl_seconds: float = DEFAULT_CUBE_CATALOG_TTL_SECONDS,
        icon_cache_invalidator: Callable[[], None] | None = None,
        classification_cache: CubeClassificationCacheRepository | None = None,
        target_key: str = "",
        definition_cache_maximum_entries: int = (
            _DEFAULT_DEFINITION_CACHE_MAXIMUM_ENTRIES
        ),
    ) -> None:
        """Create service with injected repository port."""

        self._cube_repository: CubeRepository = cube_repository
        self._catalog_ttl_seconds = max(0.0, catalog_ttl_seconds)
        self._icon_cache_invalidator = icon_cache_invalidator
        self._classification_cache = classification_cache
        self._target_key = target_key
        self._definition_cache_maximum_entries = max(
            0,
            definition_cache_maximum_entries,
        )
        self._definition_cache: OrderedDict[str, LoadedCubeDefinition] = OrderedDict()
        self._definition_cache_aliases: dict[str, str] = {}
        self._definition_cache_version_aliases: dict[tuple[str, str], str] = {}
        self._definition_cache_lock = Lock()
        self._loaded_definition_single_flight: BlockingSingleFlight[
            str, LoadedCubeDefinition
        ] = BlockingSingleFlight()

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """List selectable cubes from active repository."""

        return self._cube_repository.list_available_cubes()

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """List versions available for one cube id."""

        versions = self._cube_repository.list_cube_versions(cube_id)
        log_info(
            _LOGGER,
            "Listed cube versions",
            cube_id=cube_id,
            version_count=len(versions),
        )
        return versions

    def picker_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return the immediate picker catalog snapshot without warm-cache blocking."""

        repository = self._cube_repository
        if not isinstance(repository, CachedCubeCatalogRepository):
            entries = repository.list_available_cubes()
            return CubeCatalogSnapshot(
                entries=entries, state="fresh", source_timestamp=time()
            )
        snapshot = repository.cached_catalog_snapshot()
        normalized = self._with_ttl_state(snapshot)
        log_info(
            _LOGGER,
            "Read cube picker catalog snapshot",
            catalog_state=normalized.state,
            cube_count=len(normalized.entries),
            has_error=normalized.error is not None,
        )
        return normalized

    def refresh_picker_catalog(self) -> CubeCatalogSnapshot:
        """Force-refresh picker catalog data for background or manual refresh."""

        started_at = perf_counter()
        repository = self._cube_repository
        if isinstance(repository, CachedCubeCatalogRepository):
            snapshot = repository.refresh_catalog_snapshot()
        else:
            snapshot = CubeCatalogSnapshot(
                entries=repository.list_available_cubes(),
                state="fresh",
                source_timestamp=time(),
            )
        normalized = self._with_ttl_state(snapshot)
        log_timing(
            _LOGGER,
            "Refreshed cube picker catalog snapshot",
            started_at=started_at,
            catalog_state=normalized.state,
            cube_count=len(normalized.entries),
            has_error=normalized.error is not None,
            level="debug",
        )
        return normalized

    def invalidate_catalog_cache(self) -> None:
        """Invalidate cached picker catalog and icon asset data after mutations."""

        repository = self._cube_repository
        if isinstance(repository, CachedCubeCatalogRepository):
            repository.invalidate_cache()
            log_info(_LOGGER, "Invalidated cube picker catalog cache")
        if self._icon_cache_invalidator is None:
            self.clear_loaded_definition_cache()
            self._invalidate_classification_cache()
            return
        try:
            self._icon_cache_invalidator()
            log_info(_LOGGER, "Invalidated cube picker icon asset cache")
        except Exception:
            log_exception(_LOGGER, "Failed to invalidate cube picker icon asset cache")
        self._invalidate_classification_cache()
        self.clear_loaded_definition_cache()

    def clear_loaded_definition_cache(self) -> int:
        """Clear process-local loaded cube definition cache rows."""

        with self._definition_cache_lock:
            cleared_count = len(self._definition_cache)
            self._definition_cache.clear()
            self._definition_cache_aliases.clear()
            self._definition_cache_version_aliases.clear()
        if cleared_count:
            log_info(
                _LOGGER,
                "Invalidated loaded cube definition process cache",
                cleared_count=cleared_count,
            )
        return cleared_count

    def classify_picker_cubes(
        self,
        entries: list[CubeCatalogRecord],
    ) -> dict[str, CubePickerClassification]:
        """Classify picker cubes from loaded cube documents via the repository path."""

        started_at = perf_counter()
        classifications: dict[str, CubePickerClassification] = {}
        cache_hits = 0
        cache_misses = 0
        cache_writes = 0
        for entry in entries:
            phase_started_at = perf_counter()
            cache_key = self._classification_cache_key(entry)
            cached = self._read_cached_classification(cache_key, entry)
            if cached is not None:
                classifications[entry.cube_id] = cached
                cache_hits += 1
                log_timing(
                    _LOGGER,
                    "Used cached cube picker classification",
                    started_at=phase_started_at,
                    cube_id=entry.cube_id,
                    display_name=entry.display_name,
                    catalog_revision=entry.catalog_revision,
                    content_hash=entry.content_hash,
                    cube_version=entry.version,
                    level="debug",
                )
                continue
            cache_misses += 1
            try:
                cube_record = self._cube_repository.load_cube(entry.cube_id)
                classification = classify_cube_document(cube_record.graph)
                classifications[entry.cube_id] = classification
                if self._write_cached_classification(
                    cache_key,
                    classification,
                    entry,
                ):
                    cache_writes += 1
                log_timing(
                    _LOGGER,
                    "Classified cube picker record",
                    started_at=phase_started_at,
                    cube_id=entry.cube_id,
                    display_name=entry.display_name,
                    catalog_revision=entry.catalog_revision,
                    content_hash=entry.content_hash,
                    classified=True,
                    level="debug",
                )
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Unable to classify cube for picker",
                    cube_id=entry.cube_id,
                    error=repr(error),
                )
        log_timing(
            _LOGGER,
            "Classified cube picker records",
            started_at=started_at,
            cube_count=len(entries),
            classified_count=len(classifications),
            cache_hit_count=cache_hits,
            cache_miss_count=cache_misses,
            cache_write_count=cache_writes,
            level="debug",
        )
        return classifications

    def _classification_cache_key(
        self,
        entry: CubeCatalogRecord,
    ) -> CubeClassificationCacheKey:
        """Return the durable classification cache key for one catalog entry."""

        return CubeClassificationCacheKey(
            target_key=self._target_key,
            catalog_revision=entry.catalog_revision,
            cube_id=entry.cube_id,
            cube_content_hash=entry.content_hash,
            cube_version=entry.version,
            algorithm_version=_CLASSIFICATION_ALGORITHM_VERSION,
        )

    def _read_cached_classification(
        self,
        key: CubeClassificationCacheKey,
        entry: CubeCatalogRecord,
    ) -> CubePickerClassification | None:
        """Return a cached picker classification for one entry when available."""

        if self._classification_cache is None:
            return None
        try:
            cached = self._classification_cache.read_classification(key)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Cube picker classification cache read failed",
                cube_id=entry.cube_id,
                error=repr(error),
            )
            return None
        if cached is None:
            return None
        try:
            return _classification_from_cached(cached)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Cube picker classification cache payload was invalid",
                cube_id=entry.cube_id,
                error=repr(error),
            )
            return None

    def _write_cached_classification(
        self,
        key: CubeClassificationCacheKey,
        classification: CubePickerClassification,
        entry: CubeCatalogRecord,
    ) -> bool:
        """Persist one picker classification cache row when configured."""

        if self._classification_cache is None:
            return False
        try:
            self._classification_cache.write_classification(
                key,
                _classification_to_cached(classification),
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Cube picker classification cache write failed",
                cube_id=entry.cube_id,
                error=repr(error),
            )
            return False
        return True

    def _invalidate_classification_cache(self) -> None:
        """Delete target-scoped durable picker classification rows."""

        if self._classification_cache is None:
            return
        try:
            deleted_count = self._classification_cache.delete_for_target(
                self._target_key
            )
            log_info(
                _LOGGER,
                "Invalidated cube picker classification cache",
                target_key=self._target_key,
                deleted_count=deleted_count,
            )
        except Exception:
            log_exception(_LOGGER, "Failed to invalidate cube classification cache")

    def _with_ttl_state(self, snapshot: CubeCatalogSnapshot) -> CubeCatalogSnapshot:
        """Apply application-owned TTL policy to a repository catalog snapshot."""

        if snapshot.state != "fresh" or snapshot.source_timestamp is None:
            return snapshot
        if time() - snapshot.source_timestamp <= self._catalog_ttl_seconds:
            return snapshot
        return CubeCatalogSnapshot(
            entries=snapshot.entries,
            state="stale",
            source_timestamp=snapshot.source_timestamp,
            error=snapshot.error,
            catalog_revision=snapshot.catalog_revision,
        )

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Load cube document by id, materialize it, and shape UI metadata."""

        load_started_at = perf_counter()
        normalized_cube_id = cube_id.strip()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_definition_start",
            requested_cube_id=cube_id,
            normalized_cube_id=normalized_cube_id,
            cube_load_trace_id=cube_load_trace_id,
            definition_cache_size=len(self._definition_cache),
            inflight_definition_count=(
                self._loaded_definition_single_flight.active_count
            ),
        )
        if not normalized_cube_id:
            raise ValueError("Cube id must be a non-empty string.")
        cache_key = self._loaded_definition_cache_key(normalized_cube_id)
        if cache_key is not None:
            trace_mark(
                "cube_load_service.definition_cache.lookup",
                **_loaded_definition_cache_trace_fields(
                    cache_key,
                    cube_load_trace_id=cube_load_trace_id,
                ),
            )
            cached_definition = self._read_loaded_definition_cache(
                cache_key,
                cube_load_trace_id=cube_load_trace_id,
            )
            if cached_definition is not None:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="load_service_definition_cache_hit_return",
                    requested_cube_id=normalized_cube_id,
                    cached_cube_id=cached_definition.cube_id,
                    cube_load_trace_id=cube_load_trace_id,
                )
                return cached_definition
            trace_mark(
                "cube_load_service.definition_cache.miss",
                **_loaded_definition_cache_trace_fields(
                    cache_key,
                    cube_load_trace_id=cube_load_trace_id,
                ),
            )
            return self._load_cached_definition_single_flight(
                cache_key,
                requested_cube_id=normalized_cube_id,
                cube_load_trace_id=cube_load_trace_id,
                load_started_at=load_started_at,
            )
        else:
            alias_hit = None
            if self._should_use_loaded_definition_alias_cache():
                alias_hit = self._read_loaded_definition_cache_alias(
                    normalized_cube_id,
                    cube_load_trace_id=cube_load_trace_id,
                )
            else:
                log_info(
                    _LOGGER,
                    "Skipped loaded cube definition alias cache without fresh catalog identity",
                    cube_id=normalized_cube_id,
                    target_key=self._target_key,
                    reason="catalog_capable_repository_missing_record",
                )
            if alias_hit is not None:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="load_service_definition_alias_cache_hit_return",
                    requested_cube_id=normalized_cube_id,
                    cached_cube_id=alias_hit.cube_id,
                    cube_load_trace_id=cube_load_trace_id,
                )
                return alias_hit
        loaded_definition = self._load_cube_definition_uncached(
            normalized_cube_id,
            cube_load_trace_id=cube_load_trace_id,
            load_started_at=load_started_at,
        )
        if cache_key is None:
            cache_key = self._loaded_definition_cache_key_from_definition(
                loaded_definition
            )
        if cache_key is not None:
            self._write_loaded_definition_cache(
                cache_key,
                loaded_definition,
                requested_cube_id=normalized_cube_id,
                cube_load_trace_id=cube_load_trace_id,
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="load_service_definition_return",
                requested_cube_id=normalized_cube_id,
                loaded_cube_id=loaded_definition.cube_id,
                cube_version=loaded_definition.version,
                cube_load_trace_id=cube_load_trace_id,
                wrote_cache=True,
            )
            return _copy_loaded_definition(loaded_definition)
        trace_mark(
            "cube_load_service.definition_cache.skip",
            cube_id=normalized_cube_id,
            cube_load_trace_id=cube_load_trace_id,
            reason="no_cache_key",
        )
        return loaded_definition

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Load a cube definition using a selected cube version."""

        load_started_at = perf_counter()
        normalized_cube_id = cube_id.strip()
        normalized_version = version.strip()
        if not normalized_cube_id:
            raise ValueError("Cube id must be a non-empty string.")
        if not normalized_version:
            raise ValueError(
                f"Cube version must be non-empty for {normalized_cube_id!r}."
            )
        cached_definition = self._read_loaded_definition_cache_version_alias(
            normalized_cube_id,
            normalized_version,
            cube_load_trace_id=cube_load_trace_id,
        )
        if cached_definition is not None:
            return cached_definition
        cube_record = self._cube_repository.load_cube_version(
            normalized_cube_id,
            normalized_version,
        )
        canonical_document = validate_canonical_cube_document(cube_record.graph)
        runtime_graph = materialize_cube_runtime_graph(canonical_document)
        validate_cube_contract(runtime_graph, cube_name=canonical_document.cube_id)
        node_count, unique_class_count = _runtime_graph_counts(runtime_graph)
        log_timing(
            _LOGGER,
            "Loaded cube definition by version",
            started_at=load_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
            level="debug",
        )
        ui_payload: dict[str, object] = {
            "node_behavior_runtime": None,
            "content_hash": cube_record.content_hash,
            "catalog_revision": cube_record.catalog_revision,
            "artifact_label": cube_record.artifact_label,
            "source": {
                "kind": cube_record.source.kind,
                "repo_ref": cube_record.source.repo_ref,
                "path": cube_record.source.path,
                "local_head_sha": cube_record.source.local_head_sha,
                "dirty": cube_record.source.dirty,
            },
            "canonical_cube": canonical_document.to_metadata_payload(),
        }
        if cube_record.local_path is not None:
            ui_payload["path"] = str(cube_record.local_path)
        loaded_definition = LoadedCubeDefinition(
            cube_id=canonical_document.cube_id,
            version=canonical_document.version,
            display_name=cube_record.display_name,
            graph=copy.deepcopy(runtime_graph),
            ui_payload=ui_payload,
            icon=cube_record.icon,
        )
        cache_key = self._loaded_definition_cache_key_from_definition(loaded_definition)
        if cache_key is not None:
            self._write_loaded_definition_cache(
                cache_key,
                loaded_definition,
                requested_cube_id=normalized_cube_id,
                cube_load_trace_id=cube_load_trace_id,
            )
            return _copy_loaded_definition(loaded_definition)
        return loaded_definition

    def prewarm_cube_definition_version(self, cube_id: str, version: str) -> bool:
        """Schedule target-side warming for one selected cube version."""

        normalized_cube_id = cube_id.strip()
        normalized_version = version.strip()
        if not normalized_cube_id or not normalized_version:
            return False
        return self._cube_repository.prewarm_cube_version(
            normalized_cube_id,
            normalized_version,
        )

    def _load_cube_definition_uncached(
        self,
        normalized_cube_id: str,
        *,
        cube_load_trace_id: str,
        load_started_at: float,
    ) -> LoadedCubeDefinition:
        """Load a cube definition without reading or writing process cache."""

        phase_started_at = perf_counter()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_repository_load_start",
            cube_id=normalized_cube_id,
            cube_load_trace_id=cube_load_trace_id,
        )
        cube_record = self._cube_repository.load_cube(normalized_cube_id)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_repository_load_return",
            requested_cube_id=normalized_cube_id,
            loaded_cube_id=cube_record.cube_id,
            cube_version=cube_record.version,
            display_name=cube_record.display_name,
            source_kind=cube_record.source.kind,
            catalog_revision=cube_record.catalog_revision,
            content_hash=cube_record.content_hash,
            cube_load_trace_id=cube_load_trace_id,
        )
        log_debug(
            _LOGGER,
            "Loaded cube definition repository artifact",
            event="frontend_definition_repository_loaded",
            trace_id=cube_load_trace_id,
            requested_cube_id=normalized_cube_id,
            loaded_cube_id=cube_record.cube_id,
            loaded_version=cube_record.version,
            content_hash=cube_record.content_hash,
            catalog_revision=cube_record.catalog_revision,
            source_kind=cube_record.source.kind,
            source_repo_ref=cube_record.source.repo_ref,
            source_path=cube_record.source.path,
        )
        log_timing(
            _LOGGER,
            "Loaded cube record from repository",
            started_at=phase_started_at,
            cube_id=normalized_cube_id,
            cube_load_trace_id=cube_load_trace_id,
            source_kind=cube_record.source.kind,
            artifact_label=cube_record.artifact_label,
            level="debug",
        )
        phase_started_at = perf_counter()
        canonical_document = validate_canonical_cube_document(cube_record.graph)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_canonical_validated",
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
        )
        log_timing(
            _LOGGER,
            "Validated canonical cube document",
            started_at=phase_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        phase_started_at = perf_counter()
        runtime_graph = materialize_cube_runtime_graph(canonical_document)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_runtime_graph_materialized",
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=_runtime_graph_counts(runtime_graph)[0],
        )
        log_timing(
            _LOGGER,
            "Materialized cube runtime graph",
            started_at=phase_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        phase_started_at = perf_counter()
        validate_cube_contract(runtime_graph, cube_name=canonical_document.cube_id)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_runtime_contract_validated",
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
        )
        log_timing(
            _LOGGER,
            "Validated cube runtime contract",
            started_at=phase_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        log_info(
            _LOGGER,
            "Loaded cube",
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            artifact_label=cube_record.artifact_label,
            source_kind=cube_record.source.kind,
            repo_ref=cube_record.source.repo_ref,
        )
        node_count, unique_class_count = _runtime_graph_counts(runtime_graph)
        log_timing(
            _LOGGER,
            "Loaded cube definition",
            started_at=load_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
            level="debug",
        )

        ui_payload: dict[str, object] = {
            "node_behavior_runtime": None,
            "content_hash": cube_record.content_hash,
            "catalog_revision": cube_record.catalog_revision,
            "artifact_label": cube_record.artifact_label,
            "source": {
                "kind": cube_record.source.kind,
                "repo_ref": cube_record.source.repo_ref,
                "path": cube_record.source.path,
                "local_head_sha": cube_record.source.local_head_sha,
                "dirty": cube_record.source.dirty,
            },
            "canonical_cube": canonical_document.to_metadata_payload(),
        }
        if cube_record.local_path is not None:
            ui_payload["path"] = str(cube_record.local_path)

        phase_started_at = perf_counter()
        graph_copy = copy.deepcopy(runtime_graph)
        log_timing(
            _LOGGER,
            "Copied cube runtime graph for loaded definition",
            started_at=phase_started_at,
            cube_id=canonical_document.cube_id,
            cube_version=canonical_document.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
            level="debug",
        )

        return LoadedCubeDefinition(
            cube_id=canonical_document.cube_id,
            version=canonical_document.version,
            display_name=cube_record.display_name,
            graph=graph_copy,
            ui_payload=ui_payload,
            icon=cube_record.icon,
        )

    def _loaded_definition_cache_key(
        self,
        cube_id: str,
    ) -> _LoadedDefinitionCacheKey | None:
        """Return process cache identity for a cube when catalog data is available."""

        record = self._catalog_record_for_cube(cube_id)
        if record is None:
            return None
        return _LoadedDefinitionCacheKey(
            target_key=self._target_key,
            catalog_revision=record.catalog_revision,
            cube_id=record.cube_id,
            cube_content_hash=record.content_hash,
            cube_version=record.version,
            algorithm_version=_LOADED_DEFINITION_ALGORITHM_VERSION,
        )

    def _should_use_loaded_definition_alias_cache(self) -> bool:
        """Return whether alias cache fallback is safe for this repository."""

        return not isinstance(self._cube_repository, CachedCubeCatalogRepository)

    def _loaded_definition_cache_key_from_definition(
        self,
        definition: LoadedCubeDefinition,
    ) -> _LoadedDefinitionCacheKey | None:
        """Return process cache identity from loaded repository metadata."""

        ui_payload = definition.ui_payload
        if ui_payload is None:
            return None
        catalog_revision = ui_payload.get("catalog_revision")
        content_hash = ui_payload.get("content_hash")
        if not isinstance(catalog_revision, str) or not isinstance(content_hash, str):
            return None
        if not definition.cube_id or not definition.version:
            return None
        return _LoadedDefinitionCacheKey(
            target_key=self._target_key,
            catalog_revision=catalog_revision,
            cube_id=definition.cube_id,
            cube_content_hash=content_hash,
            cube_version=definition.version,
            algorithm_version=_LOADED_DEFINITION_ALGORITHM_VERSION,
        )

    def _catalog_record_for_cube(self, cube_id: str) -> CubeCatalogRecord | None:
        """Return current catalog identity for one cube without forcing refresh."""

        try:
            repository = self._cube_repository
            if isinstance(repository, CachedCubeCatalogRepository):
                snapshot = repository.cached_catalog_snapshot()
                entries = snapshot.entries
            else:
                entries = repository.list_available_cubes()
        except Exception as error:
            log_warning(
                _LOGGER,
                "Unable to resolve cube catalog identity for definition cache",
                cube_id=cube_id,
                error=repr(error),
            )
            return None
        return next((entry for entry in entries if entry.cube_id == cube_id), None)

    def _read_loaded_definition_cache(
        self,
        key: _LoadedDefinitionCacheKey,
        *,
        cube_load_trace_id: str,
    ) -> LoadedCubeDefinition | None:
        """Return a copy-isolated cached definition for one source identity."""

        stable_key = key.stable_hash()
        with self._definition_cache_lock:
            cached = self._definition_cache.get(stable_key)
            if cached is None:
                return None
            self._definition_cache.move_to_end(stable_key)
            copied = _copy_loaded_definition(cached)
        node_count, unique_class_count = _runtime_graph_counts(copied.graph)
        log_info(
            _LOGGER,
            "Loaded cube definition process cache hit",
            cube_id=key.cube_id,
            cube_version=key.cube_version,
            cube_load_trace_id=cube_load_trace_id,
            catalog_revision=key.catalog_revision,
            content_hash=key.cube_content_hash,
            node_count=node_count,
            unique_class_count=unique_class_count,
        )
        trace_mark(
            "cube_load_service.definition_cache.hit",
            **_loaded_definition_cache_trace_fields(
                key,
                cube_load_trace_id=cube_load_trace_id,
                node_count=node_count,
                unique_class_count=unique_class_count,
            ),
        )
        return copied

    def _read_loaded_definition_cache_alias(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str,
    ) -> LoadedCubeDefinition | None:
        """Return a copy-isolated cached definition by requested cube-id alias."""

        trace_mark(
            "cube_load_service.definition_cache.alias_lookup",
            cube_id=cube_id,
            cube_load_trace_id=cube_load_trace_id,
        )
        with self._definition_cache_lock:
            stable_key = self._definition_cache_aliases.get(cube_id)
            if stable_key is None:
                trace_mark(
                    "cube_load_service.definition_cache.skip",
                    cube_id=cube_id,
                    cube_load_trace_id=cube_load_trace_id,
                    reason="no_cache_key",
                )
                return None
            cached = self._definition_cache.get(stable_key)
            if cached is None:
                self._definition_cache_aliases.pop(cube_id, None)
                trace_mark(
                    "cube_load_service.definition_cache.alias_stale",
                    cube_id=cube_id,
                    cube_load_trace_id=cube_load_trace_id,
                )
                return None
            self._definition_cache.move_to_end(stable_key)
            copied = _copy_loaded_definition(cached)
        node_count, unique_class_count = _runtime_graph_counts(copied.graph)
        log_info(
            _LOGGER,
            "Loaded cube definition process cache alias hit",
            requested_cube_id=cube_id,
            cube_id=copied.cube_id,
            cube_version=copied.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
        )
        trace_mark(
            "cube_load_service.definition_cache.alias_hit",
            cube_id=copied.cube_id,
            requested_cube_id=cube_id,
            cube_version=copied.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
        )
        return copied

    def _read_loaded_definition_cache_version_alias(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str,
    ) -> LoadedCubeDefinition | None:
        """Return a copy-isolated cached definition by requested cube id and version."""

        trace_mark(
            "cube_load_service.definition_cache.version_alias_lookup",
            cube_id=cube_id,
            cube_version=version,
            cube_load_trace_id=cube_load_trace_id,
        )
        with self._definition_cache_lock:
            stable_key = self._definition_cache_version_aliases.get((cube_id, version))
            if stable_key is None:
                return None
            cached = self._definition_cache.get(stable_key)
            if cached is None:
                self._definition_cache_version_aliases.pop((cube_id, version), None)
                trace_mark(
                    "cube_load_service.definition_cache.version_alias_stale",
                    cube_id=cube_id,
                    cube_version=version,
                    cube_load_trace_id=cube_load_trace_id,
                )
                return None
            self._definition_cache.move_to_end(stable_key)
            copied = _copy_loaded_definition(cached)
        node_count, unique_class_count = _runtime_graph_counts(copied.graph)
        log_info(
            _LOGGER,
            "Loaded cube definition process cache version alias hit",
            requested_cube_id=cube_id,
            requested_cube_version=version,
            cube_id=copied.cube_id,
            cube_version=copied.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
        )
        trace_mark(
            "cube_load_service.definition_cache.version_alias_hit",
            cube_id=copied.cube_id,
            requested_cube_id=cube_id,
            requested_cube_version=version,
            cube_version=copied.version,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
        )
        return copied

    def _write_loaded_definition_cache(
        self,
        key: _LoadedDefinitionCacheKey,
        definition: LoadedCubeDefinition,
        *,
        requested_cube_id: str,
        cube_load_trace_id: str,
    ) -> None:
        """Store one loaded definition in the process-local LRU cache."""

        if self._definition_cache_maximum_entries == 0:
            return
        stable_key = key.stable_hash()
        evicted_keys: list[str] = []
        with self._definition_cache_lock:
            self._definition_cache[stable_key] = _copy_loaded_definition(definition)
            self._definition_cache.move_to_end(stable_key)
            while len(self._definition_cache) > self._definition_cache_maximum_entries:
                evicted_key, _definition = self._definition_cache.popitem(last=False)
                evicted_keys.append(evicted_key)
            if evicted_keys:
                evicted_key_set = set(evicted_keys)
                self._definition_cache_aliases = {
                    alias: alias_stable_key
                    for alias, alias_stable_key in self._definition_cache_aliases.items()
                    if alias_stable_key not in evicted_key_set
                }
                self._definition_cache_version_aliases = {
                    alias: alias_stable_key
                    for (
                        alias,
                        alias_stable_key,
                    ) in self._definition_cache_version_aliases.items()
                    if alias_stable_key not in evicted_key_set
                }
            self._definition_cache_aliases[requested_cube_id] = stable_key
            self._definition_cache_aliases[definition.cube_id] = stable_key
            self._definition_cache_version_aliases[
                (requested_cube_id, definition.version)
            ] = stable_key
            self._definition_cache_version_aliases[
                (definition.cube_id, definition.version)
            ] = stable_key
            cache_size = len(self._definition_cache)
        log_info(
            _LOGGER,
            "Stored loaded cube definition in process cache",
            cube_id=key.cube_id,
            cube_version=key.cube_version,
            cube_load_trace_id=cube_load_trace_id,
            catalog_revision=key.catalog_revision,
            content_hash=key.cube_content_hash,
            cache_size=cache_size,
        )
        trace_mark(
            "cube_load_service.definition_cache.write",
            **_loaded_definition_cache_trace_fields(
                key,
                cube_load_trace_id=cube_load_trace_id,
                cache_size=cache_size,
            ),
        )

    def _load_cached_definition_single_flight(
        self,
        key: _LoadedDefinitionCacheKey,
        *,
        requested_cube_id: str,
        cube_load_trace_id: str,
        load_started_at: float,
    ) -> LoadedCubeDefinition:
        """Load one process-cacheable definition through execution single-flight."""

        started_at = perf_counter()
        waited = False

        def log_wait() -> None:
            """Record that this caller is sharing active load work."""

            nonlocal waited
            waited = True
            log_info(
                _LOGGER,
                "Joined in-flight loaded cube definition request",
                cube_id=key.cube_id,
                cube_version=key.cube_version,
                cube_load_trace_id=cube_load_trace_id,
                catalog_revision=key.catalog_revision,
                content_hash=key.cube_content_hash,
            )
            trace_mark(
                "cube_load_service.definition_cache.inflight_wait",
                **_loaded_definition_cache_trace_fields(
                    key,
                    cube_load_trace_id=cube_load_trace_id,
                ),
            )

        definition = self._loaded_definition_single_flight.run(
            key.stable_hash(),
            lambda: self._load_and_cache_definition_for_single_flight(
                key,
                requested_cube_id=requested_cube_id,
                cube_load_trace_id=cube_load_trace_id,
                load_started_at=load_started_at,
            ),
            on_wait=log_wait,
        )
        copied = _copy_loaded_definition(definition)
        if waited:
            log_timing(
                _LOGGER,
                "Reused in-flight loaded cube definition result",
                started_at=started_at,
                cube_id=key.cube_id,
                cube_version=key.cube_version,
                cube_load_trace_id=cube_load_trace_id,
                catalog_revision=key.catalog_revision,
                content_hash=key.cube_content_hash,
                level="debug",
            )
        return copied

    def _load_and_cache_definition_for_single_flight(
        self,
        key: _LoadedDefinitionCacheKey,
        *,
        requested_cube_id: str,
        cube_load_trace_id: str,
        load_started_at: float,
    ) -> LoadedCubeDefinition:
        """Perform the owner load for a process-cacheable cube definition."""

        cached_definition = self._read_loaded_definition_cache(
            key,
            cube_load_trace_id=cube_load_trace_id,
        )
        if cached_definition is not None:
            return cached_definition
        loaded_definition = self._load_cube_definition_uncached(
            requested_cube_id,
            cube_load_trace_id=cube_load_trace_id,
            load_started_at=load_started_at,
        )
        self._write_loaded_definition_cache(
            key,
            loaded_definition,
            requested_cube_id=requested_cube_id,
            cube_load_trace_id=cube_load_trace_id,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_definition_return",
            requested_cube_id=requested_cube_id,
            loaded_cube_id=loaded_definition.cube_id,
            cube_version=loaded_definition.version,
            cube_load_trace_id=cube_load_trace_id,
            wrote_cache=True,
        )
        return loaded_definition

    def load_cube_graph_cached(
        self,
        cube_id: str,
        loaded_cubes: MutableMapping[str, JsonObject] | None = None,
    ) -> JsonObject:
        """Load and cache immutable runtime graph definitions by cube id."""

        cache = loaded_cubes if loaded_cubes is not None else {}
        normalized_cube_id = cube_id.strip()
        if not normalized_cube_id:
            raise ValueError("Cube id must be a non-empty string.")
        if normalized_cube_id in cache:
            return copy.deepcopy(cache[normalized_cube_id])

        loaded = self.load_cube_definition(normalized_cube_id)
        cache[normalized_cube_id] = loaded.graph
        return copy.deepcopy(loaded.graph)

    def merge_cube_buffer_patch(
        self,
        *,
        cube_buffer: JsonObject,
        buffer_patch: Any,
        cube_definition: JsonObject,
    ) -> None:
        """Merge persisted patch payload into a mutable cube buffer."""

        merge_recipe_buffer(cube_buffer, buffer_patch, cube_definition)

    def create_cube_state(
        self,
        *,
        cube_id: str,
        version: str,
        display_name: str,
        alias_name: str,
        cube_definition: JsonObject,
        cube_buffer: JsonObject,
        ui_payload: dict[str, object] | None,
    ) -> CubeState:
        """Construct cube runtime state object with optional UI metadata."""

        cube_state = CubeState(
            cube_id=cube_id,
            version=version,
            alias=alias_name,
            original_cube=cube_definition,
            buffer=cube_buffer,
            display_name=display_name,
        )
        if ui_payload is not None:
            try:
                cube_state.ui = ui_payload
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Skipped cube ui payload assignment",
                    cube_id=cube_id,
                    alias=alias_name,
                    error=error,
                )
        return cube_state

    def build_loaded_cube_runtime(
        self,
        cube_id: str,
        alias_name: str,
        *,
        buffer_patch: object | None,
        runtime_state: object | None,
        loaded_cube_definition: LoadedCubeDefinition | None = None,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeRuntime:
        """Build fully prepared cube runtime state for workflow insertion."""

        runtime_started_at = perf_counter()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_runtime_start",
            requested_cube_id=cube_id,
            requested_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            has_buffer_patch=buffer_patch is not None,
            has_loaded_definition=loaded_cube_definition is not None,
            runtime_state_type=type(runtime_state).__name__ if runtime_state else "",
        )
        loaded_cube = (
            loaded_cube_definition
            if loaded_cube_definition is not None
            else self.load_cube_definition(
                cube_id,
                cube_load_trace_id=cube_load_trace_id,
            )
        )
        phase_started_at = perf_counter()
        cube_definition = copy.deepcopy(loaded_cube.graph)
        log_timing(
            _LOGGER,
            "Copied loaded cube definition for runtime state",
            started_at=phase_started_at,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        phase_started_at = perf_counter()
        cube_buffer = copy.deepcopy(cube_definition)
        log_timing(
            _LOGGER,
            "Copied loaded cube buffer for runtime state",
            started_at=phase_started_at,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        if buffer_patch is not None:
            log_info(
                _LOGGER,
                "Applying loaded recipe buffer patch to cube runtime",
                cube_id=loaded_cube.cube_id,
                cube_alias=alias_name,
                cube_load_trace_id=cube_load_trace_id,
                buffer_patch_type=type(buffer_patch).__name__,
                buffer_patch_keys=list(buffer_patch.keys())
                if isinstance(buffer_patch, Mapping)
                else (),
            )
            phase_started_at = perf_counter()
            self.merge_cube_buffer_patch(
                cube_buffer=cube_buffer,
                buffer_patch=buffer_patch,
                cube_definition=cube_definition,
            )
            log_timing(
                _LOGGER,
                "Merged loaded cube buffer patch",
                started_at=phase_started_at,
                cube_id=loaded_cube.cube_id,
                cube_alias=alias_name,
                cube_load_trace_id=cube_load_trace_id,
                level="debug",
            )
            _restore_runtime_node_class_types(
                cube_buffer=cube_buffer,
                cube_definition=cube_definition,
            )
            overlay_result = overlay_persisted_node_inputs(
                cube_buffer=cube_buffer,
                buffer_patch=buffer_patch,
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="load_service_runtime_buffer_patch_applied",
                cube_id=loaded_cube.cube_id,
                requested_alias=alias_name,
                cube_load_trace_id=cube_load_trace_id,
                buffer_patch_type=type(buffer_patch).__name__,
            )
            log_info(
                _LOGGER,
                "Applied persisted input overlay to loaded cube runtime",
                event="frontend_runtime_persisted_input_overlay",
                trace_id=cube_load_trace_id,
                cube_id=loaded_cube.cube_id,
                cube_alias=alias_name,
                restored_node_count=overlay_result.restored_node_count,
                restored_input_count=overlay_result.restored_input_count,
                restored_model_field_count=overlay_result.restored_model_field_count,
                skipped_missing_node_count=overlay_result.skipped_missing_node_count,
                skipped_class_mismatch_count=(
                    overlay_result.skipped_class_mismatch_count
                ),
            )

        phase_started_at = perf_counter()
        seed_initialization = initialize_fresh_seed_controls(
            cube_buffer,
            buffer_patch=buffer_patch,
            randint=random.randint,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_runtime_seeds_initialized",
            cube_id=loaded_cube.cube_id,
            requested_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            initialized_seed_count=seed_initialization.initialized_count,
            skipped_explicit_seed_patch_count=(
                seed_initialization.skipped_explicit_patch_count
            ),
            skipped_invalid_seed_range_count=(
                seed_initialization.skipped_invalid_range_count
            ),
        )
        log_timing(
            _LOGGER,
            "Initialized fresh cube seed controls",
            started_at=phase_started_at,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            initialized_seed_count=seed_initialization.initialized_count,
            skipped_explicit_seed_patch_count=(
                seed_initialization.skipped_explicit_patch_count
            ),
            skipped_invalid_seed_range_count=(
                seed_initialization.skipped_invalid_range_count
            ),
            level="debug",
        )

        ui_payload = (
            dict(loaded_cube.ui_payload)
            if isinstance(loaded_cube.ui_payload, dict)
            else None
        )
        if loaded_cube.icon is not None:
            if ui_payload is None:
                ui_payload = {}
            ui_payload["cube_icon"] = loaded_cube.icon
        if ui_payload is not None:
            ui_payload["node_behavior_runtime"] = runtime_state

        phase_started_at = perf_counter()
        cube_state = self.create_cube_state(
            cube_id=loaded_cube.cube_id,
            version=loaded_cube.version,
            display_name=loaded_cube.display_name,
            alias_name=alias_name,
            cube_definition=cube_definition,
            cube_buffer=cube_buffer,
            ui_payload=ui_payload,
        )
        cube_state.update_policy = _update_policy_from_buffer_patch(buffer_patch)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_service_runtime_cube_state_created",
            cube_id=loaded_cube.cube_id,
            requested_alias=alias_name,
            cube_state_alias=getattr(cube_state, "alias", None),
            cube_load_trace_id=cube_load_trace_id,
            buffer_node_count=_runtime_graph_counts(cube_buffer)[0],
            definition_node_count=_runtime_graph_counts(cube_definition)[0],
            ui_payload_keys=sorted(ui_payload) if ui_payload is not None else [],
        )
        log_info(
            _LOGGER,
            "Created loaded cube runtime state",
            event="frontend_runtime_cube_state_created",
            trace_id=cube_load_trace_id,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            version=loaded_cube.version,
            cube_state_object_id=id(cube_state),
            buffer_object_id=id(cube_buffer),
            definition_object_id=id(cube_definition),
            buffer_node_count=_runtime_graph_counts(cube_buffer)[0],
            definition_node_count=_runtime_graph_counts(cube_definition)[0],
        )
        log_timing(
            _LOGGER,
            "Created loaded cube workflow state",
            started_at=phase_started_at,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            level="debug",
        )
        loaded_runtime = LoadedCubeRuntime(
            cube_id=loaded_cube.cube_id,
            version=loaded_cube.version,
            display_name=loaded_cube.display_name,
            cube_definition=cube_definition,
            cube_buffer=cube_buffer,
            cube_state=cube_state,
            ui_payload=ui_payload,
            icon=loaded_cube.icon,
        )
        node_count, unique_class_count = _runtime_graph_counts(cube_definition)
        log_timing(
            _LOGGER,
            "Built loaded cube runtime",
            started_at=runtime_started_at,
            cube_id=loaded_cube.cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=cube_load_trace_id,
            node_count=node_count,
            unique_class_count=unique_class_count,
            buffer_patch_applied=buffer_patch is not None,
            level="debug",
        )
        return loaded_runtime


def _runtime_graph_counts(graph: Mapping[str, Any]) -> tuple[int, int]:
    """Return node and unique class counts for cube load timing logs."""

    nodes = graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return 0, 0
    class_types = {
        str(node_data.get("class_type"))
        for node_data in nodes.values()
        if isinstance(node_data, Mapping) and node_data.get("class_type") is not None
    }
    return len(nodes), len(class_types)


def _update_policy_from_buffer_patch(buffer_patch: object | None) -> CubeUpdatePolicy:
    """Return the cube update policy requested by a persisted buffer patch."""

    if not isinstance(buffer_patch, Mapping):
        return CubeUpdatePolicy.PINNED
    raw_policy = buffer_patch.get("update_policy")
    if isinstance(raw_policy, str):
        try:
            return CubeUpdatePolicy(raw_policy)
        except ValueError:
            pass
    raw_version = buffer_patch.get("version")
    if isinstance(raw_version, str) and raw_version.strip():
        return CubeUpdatePolicy.PINNED
    return CubeUpdatePolicy.FOLLOW_LATEST


def _restore_runtime_node_class_types(
    *,
    cube_buffer: JsonObject,
    cube_definition: JsonObject,
) -> int:
    """Reassert loaded cube node class identities after persisted value merge."""

    runtime_nodes = cube_buffer.get("nodes")
    definition_nodes = cube_definition.get("nodes")
    if not isinstance(runtime_nodes, Mapping) or not isinstance(
        definition_nodes, Mapping
    ):
        return 0

    restored_count = 0
    for node_name, definition_node in definition_nodes.items():
        runtime_node = runtime_nodes.get(node_name)
        if not isinstance(runtime_node, MutableMapping) or not isinstance(
            definition_node, Mapping
        ):
            continue
        definition_class_type = definition_node.get("class_type")
        if not isinstance(definition_class_type, str):
            continue
        if runtime_node.get("class_type") != definition_class_type:
            runtime_node["class_type"] = definition_class_type
            restored_count += 1
    return restored_count


def _classification_to_cached(
    classification: CubePickerClassification,
) -> CachedCubePickerClassification:
    """Convert application picker classification to a cache payload."""

    return CachedCubePickerClassification(
        input_count=classification.input_count,
        output_count=classification.output_count,
        role=classification.role,
        supported_models=classification.supported_models,
        search_terms=classification.search_terms,
        search_targets=tuple(
            CachedCubeSearchTerm(text=term.text, kind=term.kind)
            for term in classification.search_targets
        ),
    )


def _classification_from_cached(
    cached: CachedCubePickerClassification,
) -> CubePickerClassification:
    """Convert cached picker classification payload to application model."""

    if cached.role not in _CUBE_PICKER_ROLES:
        raise ValueError(f"Unsupported cached cube picker role: {cached.role!r}.")
    search_targets: list[CubeSearchTerm] = []
    for target in cached.search_targets:
        if target.kind not in _CUBE_SEARCH_TARGET_KINDS:
            raise ValueError(
                f"Unsupported cached cube search target kind: {target.kind!r}."
            )
        search_targets.append(
            CubeSearchTerm(
                text=target.text,
                kind=cast(CubeSearchTargetKind, target.kind),
            )
        )
    return CubePickerClassification(
        input_count=cached.input_count,
        output_count=cached.output_count,
        role=cast(CubePickerRole, cached.role),
        supported_models=cached.supported_models,
        search_terms=cached.search_terms,
        search_targets=tuple(search_targets),
    )


def _copy_loaded_definition(definition: LoadedCubeDefinition) -> LoadedCubeDefinition:
    """Return a copy-isolated loaded definition for cache boundaries."""

    return LoadedCubeDefinition(
        cube_id=definition.cube_id,
        version=definition.version,
        display_name=definition.display_name,
        graph=copy.deepcopy(definition.graph),
        ui_payload=(
            copy.deepcopy(definition.ui_payload)
            if definition.ui_payload is not None
            else None
        ),
        icon=definition.icon,
    )


def _text(value: object) -> str:
    """Return a stripped string value."""

    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "CubeLoadService",
    "LoadedCubeDefinition",
    "LoadedCubeRuntime",
]
