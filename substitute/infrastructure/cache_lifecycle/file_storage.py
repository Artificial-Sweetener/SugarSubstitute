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

"""Coordinate durable cache preparation and nonpersistent fallback lifetime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
import tempfile

from substitute.application.cache_lifecycle import (
    PersistentCacheCatalog,
    PreparedCacheCatalog,
    PreparedCacheNamespace,
)
from substitute.infrastructure.cache_lifecycle.generation_store import (
    CacheGenerationStore,
)
from substitute.infrastructure.cache_lifecycle.legacy_migration import (
    LegacyPersistentCacheMigrator,
)
from substitute.infrastructure.cache_lifecycle.manifest_store import (
    PersistentCacheManifestStore,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.cache_lifecycle.file_storage")
_MANAGED_DIRECTORY = "managed"
Clock = Callable[[], datetime]


class FilePersistentCacheStorage:
    """Prepare every catalog namespace beneath one installation cache root."""

    def __init__(
        self,
        cache_root: Path,
        *,
        application_version: str,
        installation_root: Path | None = None,
        legacy_model_metadata_root: Path | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Store lifecycle paths and diagnostic application identity."""

        self._cache_root = cache_root.resolve()
        self._application_version = application_version
        self._installation_root = installation_root
        self._legacy_model_metadata_root = legacy_model_metadata_root
        self._clock = clock or (lambda: datetime.now(UTC))
        self._temporary_roots: list[tempfile.TemporaryDirectory[str]] = []

    def prepare(self, catalog: PersistentCacheCatalog) -> PreparedCacheCatalog:
        """Prepare durable namespaces or isolated process-lifetime fallbacks."""

        try:
            return self._prepare_persistent(catalog)
        except OSError as error:
            log_warning(
                _LOGGER,
                "Persistent cache root is unavailable; using temporary caches.",
                cache_root=self._cache_root,
                error=repr(error),
            )
            return self._prepare_temporary(catalog)

    def close(self) -> None:
        """Release any process-lifetime temporary fallback namespaces."""

        while self._temporary_roots:
            self._temporary_roots.pop().cleanup()

    def _prepare_persistent(
        self,
        catalog: PersistentCacheCatalog,
    ) -> PreparedCacheCatalog:
        """Prepare governed generations beneath the durable cache root."""

        self._cache_root.mkdir(parents=True, exist_ok=True)
        managed_root = self._cache_root / _MANAGED_DIRECTORY
        managed_root.mkdir(parents=True, exist_ok=True)
        manifest_store = PersistentCacheManifestStore(
            self._cache_root,
            application_version=self._application_version,
            clock=self._clock,
        )
        manifest_store.validate_or_quarantine()
        generation_store = CacheGenerationStore(
            managed_root,
            clock=self._clock,
        )
        prepared = tuple(
            generation_store.prepare(registration)
            for registration in catalog.registrations
        )
        prepared_catalog = PreparedCacheCatalog(namespaces=prepared)
        LegacyPersistentCacheMigrator(
            self._cache_root,
            installation_root=self._installation_root,
            legacy_model_metadata_root=self._legacy_model_metadata_root,
        ).migrate(prepared_catalog)
        manifest_store.report_unknown_root_content(catalog)
        manifest_store.save(catalog, prepared=prepared)
        return prepared_catalog

    def _prepare_temporary(
        self,
        catalog: PersistentCacheCatalog,
    ) -> PreparedCacheCatalog:
        """Create isolated process-lifetime namespaces after durable IO failure."""

        temporary_root = tempfile.TemporaryDirectory(
            prefix="sugarsubstitute-cache-fallback-"
        )
        self._temporary_roots.append(temporary_root)
        root = Path(temporary_root.name)
        namespaces: list[PreparedCacheNamespace] = []
        for registration in catalog.registrations:
            path = root.joinpath(*registration.namespace.parts)
            path.mkdir(parents=True, exist_ok=True)
            namespaces.append(
                PreparedCacheNamespace(
                    cache_id=registration.cache_id,
                    path=path,
                    compatibility_identifier=registration.compatibility.identifier,
                    persistent=False,
                )
            )
        return PreparedCacheCatalog(namespaces=tuple(namespaces))


__all__ = ["FilePersistentCacheStorage"]
