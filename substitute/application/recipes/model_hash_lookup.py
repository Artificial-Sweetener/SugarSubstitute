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

"""Resolve recipe-serializable model hashes from cached local metadata."""

from __future__ import annotations

from collections.abc import Hashable
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
)
from substitute.application.model_metadata.ports import (
    ModelMetadataCatalogQueryRepository,
)
from substitute.domain.model_metadata import ModelMetadataCacheRecord


class RecipeModelHashLookup(Protocol):
    """Provide cache-only model hash lookups for recipe serialization."""

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return an eligible CivitAI-backed SHA256 for one local model value."""


class CachedModelCatalogLookup(Protocol):
    """Expose already-loaded picker catalog snapshots for recipe hash lookup."""

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return an in-memory model snapshot without loading missing data."""


class CachedRecipeModelHashLookup:
    """Return recipe hash comments from existing model metadata cache records."""

    def __init__(
        self,
        repository: ModelMetadataCatalogQueryRepository,
        catalog: CachedModelCatalogLookup | None = None,
    ) -> None:
        """Store the metadata cache query repository."""

        self._repository = repository
        self._catalog = catalog
        self._shared_indexes_by_kind: dict[
            str,
            tuple[Hashable, RecipeModelHashKindIndex],
        ] = {}
        self._lock = RLock()

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return an eligible CivitAI-backed SHA256 for one local model value."""

        return self.create_session().hash_for_model_value(kind=kind, value=value)

    def create_session(self) -> RecipeModelHashLookup:
        """Return an indexed cache-only lookup for repeated recipe hash queries."""

        return _CachedRecipeModelHashLookupSession(
            owner=self,
        )

    def _index_for_kind(self, kind: str) -> RecipeModelHashKindIndex:
        """Return a process-scoped index for one kind when a revision is available."""

        cache_token = _shared_cache_token(
            repository=self._repository,
            catalog=self._catalog,
            kind=kind,
        )
        if cache_token is None:
            return _build_index(
                repository=self._repository,
                catalog=self._catalog,
                kind=kind,
            )
        with self._lock:
            cached = self._shared_indexes_by_kind.get(kind)
            if cached is not None and cached[0] == cache_token:
                return cached[1]
        index = _build_index(
            repository=self._repository,
            catalog=self._catalog,
            kind=kind,
        )
        with self._lock:
            self._shared_indexes_by_kind[kind] = (cache_token, index)
        return index


@dataclass(frozen=True, slots=True)
class RecipeModelHashKindIndex:
    """Index recipe-eligible hashes for one model kind."""

    sha_by_backend_value: Mapping[str, str]
    eligible_sha_values: frozenset[str]


class _CachedRecipeModelHashLookupSession:
    """Reuse recipe hash indexes across many lookups in one serialization run."""

    def __init__(
        self,
        *,
        owner: CachedRecipeModelHashLookup,
    ) -> None:
        """Store cache-only collaborators and per-kind indexes."""

        self._owner = owner
        self._indexes_by_kind: dict[str, RecipeModelHashKindIndex] = {}

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return an eligible CivitAI-backed SHA256 for one local model value."""

        index = self._index_for_kind(kind)
        return index.sha_by_backend_value.get(value.casefold())

    @property
    def indexed_kind_count(self) -> int:
        """Return how many model kinds have been indexed in this session."""

        return len(self._indexes_by_kind)

    def _index_for_kind(self, kind: str) -> RecipeModelHashKindIndex:
        """Return the cached index for one model kind, building it on first use."""

        index = self._indexes_by_kind.get(kind)
        if index is None:
            index = self._owner._index_for_kind(kind)
            self._indexes_by_kind[kind] = index
        return index


def _build_index(
    *,
    repository: ModelMetadataCatalogQueryRepository,
    catalog: CachedModelCatalogLookup | None,
    kind: str,
) -> RecipeModelHashKindIndex:
    """Build a casefolded backend-value index from eligible cache records."""

    records = repository.list_records(kind=kind)
    sha_by_backend_value: dict[str, str] = {}
    eligible_sha_values: set[str] = set()
    for record in records:
        if not _record_is_recipe_hash_eligible(record):
            continue
        sha256 = record.local.sha256.upper()
        eligible_sha_values.add(sha256)
        sha_by_backend_value.setdefault(record.local.value.casefold(), sha256)
    if catalog is not None and eligible_sha_values:
        cached_models = catalog.cached_models(kind)
        if cached_models is not None:
            _add_cached_catalog_hashes(
                sha_by_backend_value=sha_by_backend_value,
                eligible_sha_values=frozenset(eligible_sha_values),
                cached_models=cached_models,
            )
    return RecipeModelHashKindIndex(
        sha_by_backend_value=sha_by_backend_value,
        eligible_sha_values=frozenset(eligible_sha_values),
    )


def _shared_cache_token(
    *,
    repository: ModelMetadataCatalogQueryRepository,
    catalog: CachedModelCatalogLookup | None,
    kind: str,
) -> Hashable | None:
    """Return a shared-cache token, or ``None`` when safe invalidation is unavailable."""

    repository_revision = _repository_revision(repository, kind)
    if repository_revision is None:
        return None
    return repository_revision, _catalog_revision(catalog, kind)


def _repository_revision(
    repository: ModelMetadataCatalogQueryRepository,
    kind: str,
) -> Hashable | None:
    """Return a cheap metadata revision token when the repository exposes one."""

    revision = getattr(repository, "recipe_hash_revision", None)
    if not callable(revision):
        return None
    value = revision(kind=kind)
    return value if isinstance(value, Hashable) else repr(value)


def _catalog_revision(
    catalog: CachedModelCatalogLookup | None,
    kind: str,
) -> Hashable:
    """Return a token for in-memory catalog fallback rows."""

    if catalog is None:
        return ("catalog", None)
    cached_snapshot = getattr(catalog, "cached_snapshot", None)
    if callable(cached_snapshot):
        snapshot = cached_snapshot(kind)
        if snapshot is None:
            return ("catalog_snapshot", None)
        generation = getattr(snapshot, "generation", None)
        if isinstance(generation, Hashable):
            return ("catalog_snapshot", generation)
    cached_models = catalog.cached_models(kind)
    if cached_models is None:
        return ("catalog_models", None)
    return ("catalog_models", len(cached_models))


def _add_cached_catalog_hashes(
    *,
    sha_by_backend_value: dict[str, str],
    eligible_sha_values: frozenset[str],
    cached_models: tuple[ModelCatalogItem, ...],
) -> None:
    """Add cached picker values whose SHA is backed by eligible metadata."""

    for item in cached_models:
        if not item.sha256:
            continue
        sha256 = item.sha256.upper()
        if sha256 not in eligible_sha_values:
            continue
        sha_by_backend_value.setdefault(item.backend_value.casefold(), sha256)


def _record_is_recipe_hash_eligible(record: ModelMetadataCacheRecord) -> bool:
    """Return whether one cached record can safely emit a recipe hash comment."""

    if record.provider_status != "found" or record.provider is None:
        return False
    local_hash = record.local.sha256.upper()
    for file in record.provider.files:
        raw_file_hash = file.hashes.get("SHA256") or file.hashes.get("sha256")
        if isinstance(raw_file_hash, str) and raw_file_hash.upper() == local_hash:
            return True
    return False


__all__ = [
    "CachedModelCatalogLookup",
    "CachedRecipeModelHashLookup",
    "RecipeModelHashKindIndex",
    "RecipeModelHashLookup",
]
